import asyncio, json, os, random, sqlite3, html, logging
from pathlib import Path
from contextlib import closing
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('BOT_TOKEN environment variable is missing')

BASE = Path(__file__).resolve().parent
DB = BASE / 'zonacarcase_v2.db'
CARS = json.loads((BASE / 'cars.json').read_text(encoding='utf-8'))
CAR_BY_ID = {c['id']: c for c in CARS}
RARITY = {
    'Common': ('⚪', 60.0, 0.35), 'Uncommon': ('🟢', 25.0, 0.40),
    'Rare': ('🔵', 10.0, 0.50), 'Epic': ('🟣', 3.0, 0.60),
    'Legendary': ('🟡', 1.5, 0.70), 'Exclusive': ('🔴', 0.4, 0.80),
    'Secret': ('⚫', 0.1, 1.00)
}
RARITY_ORDER = list(RARITY)
CASE_PRICE = 2500
DAILY_REWARD = 5000
logging.basicConfig(level=logging.INFO)


def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=20000')
    return con


def init_db():
    with closing(db()) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER NOT NULL DEFAULT 10000,
          xp INTEGER NOT NULL DEFAULT 0, cases_opened INTEGER NOT NULL DEFAULT 0,
          daily_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS garage(
          user_id INTEGER NOT NULL, car_id TEXT NOT NULL, qty INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(user_id, car_id)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        ''')
        con.commit()


def money(n): return f'${n:,.0f}'

def user(uid, username=None):
    with closing(db()) as con:
        row=con.execute('SELECT * FROM users WHERE user_id=?',(uid,)).fetchone()
        if not row:
            con.execute('INSERT INTO users(user_id,username) VALUES(?,?)',(uid,username or ''))
            con.commit(); row=con.execute('SELECT * FROM users WHERE user_id=?',(uid,)).fetchone()
        elif username is not None:
            con.execute('UPDATE users SET username=? WHERE user_id=?',(username,uid)); con.commit()
        return row


def pick_car():
    r=random.random()*100
    acc=0
    rarity='Secret'
    for name,(_,chance,_) in RARITY.items():
        acc+=chance
        if r<=acc: rarity=name; break
    pool=[c for c in CARS if c['rarity']==rarity]
    return random.choice(pool)


def add_car(uid,cid):
    with closing(db()) as con:
        con.execute('INSERT INTO garage(user_id,car_id,qty) VALUES(?,?,1) ON CONFLICT(user_id,car_id) DO UPDATE SET qty=qty+1',(uid,cid)); con.commit()

def owned(uid,cid):
    with closing(db()) as con:
        r=con.execute('SELECT qty FROM garage WHERE user_id=? AND car_id=?',(uid,cid)).fetchone(); return r['qty'] if r else 0

def set_balance(uid,delta):
    with closing(db()) as con:
        cur=con.execute('UPDATE users SET balance=balance+? WHERE user_id=? AND balance+?>=0',(delta,uid,delta)); con.commit(); return cur.rowcount==1

def add_xp(uid,x):
    with closing(db()) as con:
        con.execute('UPDATE users SET xp=xp+? WHERE user_id=?',(x,uid)); con.commit()

def format_car(c, qty=None):
    em=RARITY[c['rarity']][0]
    s=(f"{em} <b>{html.escape(c['name'])}</b>\n\n"
       f"📅 Год: <b>{c['year']}</b>\n"
       f"⚡ Мощность: <b>{c['power_hp']} л.с.</b>\n"
       f"💵 Цена: <b>{money(c['price_usd'])}</b>\n"
       f"💎 Редкость: <b>{c['rarity']}</b>")
    if qty is not None: s += f"\n🚗 В гараже: <b>{qty} шт.</b>"
    return s

async def photo_url(session, car):
    queries=[car['name'], f"{car['brand']} {car['model']} car"]
    for q in queries:
        try:
            params={'action':'query','generator':'search','gsrsearch':q,'gsrnamespace':'6','gsrlimit':5,'prop':'imageinfo','iiprop':'url','iiurlwidth':900,'format':'json'}
            async with session.get('https://commons.wikimedia.org/w/api.php',params=params,timeout=10) as r:
                data=await r.json(content_type=None)
            pages=(data.get('query') or {}).get('pages') or {}
            for p in pages.values():
                info=(p.get('imageinfo') or [{}])[0]
                url=info.get('thumburl') or info.get('url')
                if url and any(x in url.lower() for x in ['.jpg','.jpeg','.png','.webp']): return url
        except Exception: pass
    return None

async def send_car(bot, chat_id, car, caption):
    async with aiohttp.ClientSession() as session:
        url=await photo_url(session,car)
    if url:
        try:
            await bot.send_photo(chat_id,url,caption=caption,parse_mode='HTML'); return
        except Exception: pass
    await bot.send_message(chat_id,caption,parse_mode='HTML')


def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📦 Кейс',callback_data='case'),InlineKeyboardButton(text='🏠 Гараж',callback_data='garage:0')],
        [InlineKeyboardButton(text='👤 Профиль',callback_data='profile'),InlineKeyboardButton(text='🎁 Бонус',callback_data='daily')],
        [InlineKeyboardButton(text='🏆 Топ',callback_data='top'),InlineKeyboardButton(text='ℹ️ Помощь',callback_data='help')]
    ])

def car_kb(cid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💰 Продать',callback_data=f'sell:{cid}'),InlineKeyboardButton(text='◀️ Назад',callback_data='garage:0')]])

dp=Dispatcher()

@dp.message(CommandStart())
async def start(m:Message):
    user(m.from_user.id,m.from_user.username)
    await m.answer(f"🚘 <b>Zona_CarCase</b>\n\nНовая версия коллекционной игры.\n\n💵 Стартовый баланс: <b>{money(10000)}</b>\n🚗 Машин в коллекции: <b>306</b>\n\nОткрывай кейсы, собирай машины и поднимайся в топ!",reply_markup=main_kb(),parse_mode='HTML')

@dp.message(Command('help'))
async def help_cmd(m:Message): await m.answer('📖 <b>Команды</b>\n/start — главное меню\n/help — помощь\n/profile — профиль\n/case — открыть кейс\n/garage — гараж\n/daily — ежедневный бонус\n/top — рейтинг',parse_mode='HTML')

@dp.message(Command('profile'))
async def profile_cmd(m:Message): await profile(m)
@dp.message(Command('case'))
async def case_cmd(m:Message): await open_case(m)
@dp.message(Command('garage'))
async def garage_cmd(m:Message): await garage(m,0)
@dp.message(Command('daily'))
async def daily_cmd(m:Message): await daily(m)
@dp.message(Command('top'))
async def top_cmd(m:Message): await top(m)

@dp.callback_query(F.data=='profile')
async def profile_cb(c:CallbackQuery): await c.answer(); await profile(c.message)
async def profile(m:Message):
    u=user(m.from_user.id,m.from_user.username)
    with closing(db()) as con:
        unique=con.execute('SELECT COUNT(*) n FROM garage WHERE user_id=? AND qty>0',(m.from_user.id,)).fetchone()['n']
        total=con.execute('SELECT COALESCE(SUM(qty),0) n FROM garage WHERE user_id=?',(m.from_user.id,)).fetchone()['n']
    lvl=u['xp']//1000+1
    await m.answer(f"👤 <b>ПРОФИЛЬ</b>\n\n💵 Баланс: <b>{money(u['balance'])}</b>\n⭐ Уровень: <b>{lvl}</b>\n✨ XP: <b>{u['xp']}</b>\n\n🚗 Уникальных: <b>{unique}/306</b>\n📦 Всего машин: <b>{total}</b>\n🎁 Открыто кейсов: <b>{u['cases_opened']}</b>",parse_mode='HTML',reply_markup=main_kb())

@dp.callback_query(F.data=='case')
async def case_cb(c:CallbackQuery): await c.answer(); await open_case(c.message)
async def open_case(m:Message):
    user(m.from_user.id,m.from_user.username)
    if not set_balance(m.from_user.id,-CASE_PRICE):
        await m.answer(f'❌ Нужно {money(CASE_PRICE)} для открытия кейса.'); return
    car=pick_car(); add_car(m.from_user.id,car['id']); add_xp(m.from_user.id,50)
    with closing(db()) as con: con.execute('UPDATE users SET cases_opened=cases_opened+1 WHERE user_id=?',(m.from_user.id,)); con.commit()
    cap='🎉 <b>МАШИНА ВЫПАЛА!</b>\n\n'+format_car(car,owned(m.from_user.id,car['id']))+f'\n\n📦 Стоимость кейса: <b>{money(CASE_PRICE)}</b>'
    await send_car(m.bot,m.chat.id,car,cap)

@dp.callback_query(F.data.startswith('garage:'))
async def garage_cb(c:CallbackQuery): await c.answer(); await garage(c.message,int(c.data.split(':')[1]))
async def garage(m:Message,page=0):
    uid=m.from_user.id
    with closing(db()) as con:
        rows=con.execute('SELECT car_id,qty FROM garage WHERE user_id=? AND qty>0 ORDER BY car_id',(uid,)).fetchall()
    if not rows: await m.answer('🏠 Гараж пуст. Открой первый кейс!',reply_markup=main_kb()); return
    page=max(0,min(page,(len(rows)-1)//8)); chunk=rows[page*8:(page+1)*8]
    buttons=[]
    for r in chunk:
        car=CAR_BY_ID[r['car_id']]; buttons.append([InlineKeyboardButton(text=f"{RARITY[car['rarity']][0]} {car['name']} ×{r['qty']}",callback_data=f"car:{car['id']}")])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'garage:{page-1}'))
    if (page+1)*8<len(rows): nav.append(InlineKeyboardButton(text='➡️',callback_data=f'garage:{page+1}'))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(text='🏠 Меню',callback_data='home')])
    await m.answer(f'🏠 <b>ГАРАЖ</b>\nСтраница {page+1}/{(len(rows)+7)//8}\nВыбери машину:',reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),parse_mode='HTML')

@dp.callback_query(F.data.startswith('car:'))
async def car_cb(c:CallbackQuery):
    await c.answer(); car=CAR_BY_ID.get(c.data.split(':',1)[1]);
    if not car: return
    q=owned(c.from_user.id,car['id'])
    await send_car(c.bot,c.message.chat.id,car,format_car(car,q))

@dp.callback_query(F.data.startswith('sell:'))
async def sell_cb(c:CallbackQuery):
    await c.answer(); cid=c.data.split(':',1)[1]; car=CAR_BY_ID.get(cid)
    if not car or owned(c.from_user.id,cid)<=0: await c.message.answer('❌ Машины нет в гараже.'); return
    with closing(db()) as con:
        cur=con.execute('UPDATE garage SET qty=qty-1 WHERE user_id=? AND car_id=? AND qty>0',(c.from_user.id,cid));
        con.execute('DELETE FROM garage WHERE user_id=? AND car_id=? AND qty<=0',(c.from_user.id,cid)); con.commit()
    gain=int(car['price_usd']*RARITY[car['rarity']][2]); set_balance(c.from_user.id,gain)
    await c.message.answer(f'💰 Продано: <b>{car["name"]}</b>\nПолучено: <b>{money(gain)}</b>',parse_mode='HTML')

@dp.callback_query(F.data=='daily')
async def daily_cb(c:CallbackQuery): await c.answer(); await daily(c.message)
async def daily(m:Message):
    import time; now=int(time.time()); u=user(m.from_user.id,m.from_user.username)
    if now-u['daily_at']<86400:
        left=86400-(now-u['daily_at']); await m.answer(f'⏳ Следующий бонус через <b>{left//3600}ч {(left%3600)//60}м</b>.',parse_mode='HTML'); return
    with closing(db()) as con:
        con.execute('UPDATE users SET balance=balance+?, daily_at=? WHERE user_id=?',(DAILY_REWARD,now,m.from_user.id)); con.commit()
    await m.answer(f'🎁 Ежедневный бонус: <b>+{money(DAILY_REWARD)}</b>')

@dp.callback_query(F.data=='top')
async def top_cb(c:CallbackQuery): await c.answer(); await top(c.message)
async def top(m:Message):
    with closing(db()) as con: rows=con.execute('SELECT username,balance,xp FROM users ORDER BY balance DESC LIMIT 10').fetchall()
    text='🏆 <b>ТОП-10</b>\n\n'+ '\n'.join(f"{i}. @{html.escape(r['username'] or 'player')} — {money(r['balance'])} · ⭐{r['xp']}" for i,r in enumerate(rows,1))
    await m.answer(text,parse_mode='HTML')

@dp.callback_query(F.data=='help')
async def help_cb(c:CallbackQuery): await c.answer(); await help_cmd(c.message)
@dp.callback_query(F.data=='home')
async def home_cb(c:CallbackQuery): await c.answer(); await start(c.message)

async def main():
    init_db(); bot=Bot(TOKEN); await bot.delete_webhook(drop_pending_updates=True); logging.info('Loaded cars: %s',len(CARS)); await dp.start_polling(bot)

if __name__=='__main__': asyncio.run(main())
