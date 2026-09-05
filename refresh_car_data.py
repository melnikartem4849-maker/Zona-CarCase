import asyncio, json, re
from pathlib import Path
import aiohttp

DATA=Path('car_data.json')
WIKI='https://en.wikipedia.org/w/api.php'

POWER_RE=re.compile(r'(?:power|engine power|output|horsepower|hp)\s*=\s*(?:[^\n]*?)(\d{2,4})\s*(?:hp|PS|bhp|kW)', re.I)
PRICE_RE=re.compile(r'(?:price|msrp|base price|starting price)\s*=\s*[^\n]*?(?:US\$|\$|USD)\s*([0-9][0-9,]*)', re.I)
CURRENCY_RE=re.compile(r'(?:US\$|\$|USD)\s*([0-9][0-9,]*)', re.I)

def clean_wikitext(t):
    t=re.sub(r'<ref[^>]*>.*?</ref>', '', t, flags=re.S|re.I)
    t=re.sub(r'\{\{[^{}]*\}\}', ' ', t)
    return t

async def get_json(session, params):
    async with session.get(WIKI, params=params) as r:
        return await r.json()

async def search_page(session, title):
    params={'action':'query','format':'json','list':'search','srsearch':title,'srlimit':3,'srnamespace':0}
    data=await get_json(session,params)
    hits=data.get('query',{}).get('search',[])
    return hits[0]['title'] if hits else None

async def page_wikitext(session, title):
    params={'action':'parse','format':'json','page':title,'prop':'wikitext','formatversion':2}
    data=await get_json(session,params)
    return data.get('parse',{}).get('wikitext','')

async def one(session, item, sem):
    async with sem:
        title=await search_page(session, item['name'])
        if not title:
            return item
        wt=clean_wikitext(await page_wikitext(session,title))
        power=None; price=None
        m=POWER_RE.search(wt)
        if m:
            power=int(m.group(1))
        # Prefer an infobox price/MSRP line; otherwise use first dollar value near pricing terms.
        m=PRICE_RE.search(wt)
        if m:
            price=int(m.group(1).replace(',',''))
        else:
            lines=wt.splitlines()
            for i,line in enumerate(lines):
                if re.search(r'\b(msrp|price|starting price|base price)\b', line, re.I):
                    block=' '.join(lines[i:i+3])
                    m=CURRENCY_RE.search(block)
                    if m:
                        price=int(m.group(1).replace(',','')); break
        out=dict(item)
        out['source']='https://en.wikipedia.org/wiki/'+title.replace(' ','_')
        if power: out['power']=power
        if price: out['price']=price
        return out

async def main():
    cars=json.loads(DATA.read_text(encoding='utf-8'))
    timeout=aiohttp.ClientTimeout(total=30)
    sem=asyncio.Semaphore(5)
    async with aiohttp.ClientSession(timeout=timeout, headers={'User-Agent':'Zona_CarCase/1.0'}) as s:
        results=[]
        for i in range(0,len(cars),20):
            batch=cars[i:i+20]
            done=await asyncio.gather(*(one(s,x,sem) for x in batch))
            results.extend(done)
            print(f'{min(i+20,len(cars))}/{len(cars)}')
    DATA.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    missing=[x for x in results if not x.get('power') or not x.get('price')]
    Path('car_data_missing.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Готово. Не найдено полных данных:',len(missing))
    print('Список:', 'car_data_missing.json')

if __name__=='__main__':
    asyncio.run(main())
