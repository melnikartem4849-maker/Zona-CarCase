import asyncio
import logging
import os
import random
import sqlite3
import time
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


dp = Dispatcher()


class AddCarState(StatesGroup):
    name = State()
    year = State()
    power = State()
    price = State()
    rarity = State()
    photo = State()


class GiveCarState(StatesGroup):
    user_id = State()
    car = State()



# =========================================================
# НАСТРОЙКИ
# =========================================================
# ВАЖНО: не вставляй токен прямо в код.
# Перед запуском в CMD выполни:
# set BOT_TOKEN="ТВОЙ_ТОКЕН"
TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "zonacarcase.db"
CASE_PRICE = 1_200_000
CASE_COOLDOWN = 3 * 60 * 60  # 3 часа
AUCTION_INTERVAL = 60 * 60  # новый лот каждый час
AUCTION_BID_TIME = 60  # 1 минута после каждой ставки
AUCTION_MIN_BID = 1_000_000
AUCTION_BID_STEP = 500_000
ADMIN_ID = 5474546385

# Контейнеры: покупаются отдельно от обычного кейса.
# Внутри каждого контейнера выпадает 1 машина из указанных редкостей.
CONTAINERS = {
    "standard": {
        "name": "Авто-контейнер",
        "emoji": "📦",
        "price": 2_500_000,
        "rarities": ["Rare", "Epic", "Legendary"],
    },
    "premium": {
        "name": "Премиум-контейнер",
        "emoji": "💜",
        "price": 12_000_000,
        "rarities": ["Epic", "Legendary", "Exclusive"],
    },
    "exclusive": {
        "name": "Эксклюзив-контейнер",
        "emoji": "🔴",
        "price": 60_000_000,
        "rarities": ["Legendary", "Exclusive", "Secret"],
    },
}

RARITIES = {
    "Common":    {"emoji": "⚪", "chance": 60.0, "sell": 0.35},
    "Uncommon":  {"emoji": "🟢", "chance": 25.0, "sell": 0.40},
    "Rare":      {"emoji": "🔵", "chance": 10.0, "sell": 0.50},
    "Epic":      {"emoji": "🟣", "chance": 3.0,  "sell": 0.60},
    "Legendary": {"emoji": "🟡", "chance": 1.5,  "sell": 0.70},
    "Exclusive": {"emoji": "🔴", "chance": 0.4,  "sell": 0.80},
    "Secret":    {"emoji": "⚫", "chance": 0.1,  "sell": 1.00},
}

# 34 бренда × 9 моделей = 306 автомобилей.
# Редкость распределяется по автомобилям после создания списка.
BRAND_MODELS = {
    "Volkswagen": ["Golf GTI", "Golf R", "Passat R-Line", "Arteon R", "Polo GTI", "T-Roc R", "Tiguan R", "Touareg R", "Scirocco R"],
    "BMW": ["M2", "M3", "M4", "M5", "M8", "X3 M", "X5 M", "Z4 M40i", "i8"],
    "Mercedes-Benz": ["A45 AMG", "C63 AMG", "E63 AMG", "S63 AMG", "AMG GT", "GT 63 S", "G63 AMG", "SL63 AMG", "EQS 53"],
    "Audi": ["S3", "S4", "S5", "RS3", "RS4", "RS5", "RS6 Avant", "RS7", "R8 V10"],
    "Porsche": ["718 Cayman", "718 Boxster", "911 Carrera", "911 Turbo S", "911 GT3", "911 GT3 RS", "Taycan Turbo S", "Panamera Turbo S", "Cayenne Turbo GT"],
    "Ferrari": ["Roma", "Portofino M", "F8 Tributo", "F8 Spider", "296 GTB", "296 GTS", "812 Superfast", "SF90 Stradale", "LaFerrari"],
    "Lamborghini": ["Huracan EVO", "Huracan STO", "Huracan Tecnica", "Urus", "Urus Performante", "Revuelto", "Aventador SVJ", "Aventador S", "Sian"],
    "McLaren": ["570S", "600LT", "720S", "765LT", "Artura", "GT", "750S", "Senna", "Speedtail"],
    "Aston Martin": ["Vantage", "DB11", "DB12", "DBS", "Vanquish", "Valkyrie", "Valhalla", "Rapide S", "One-77"],
    "Bentley": ["Continental GT", "Continental GTC", "Flying Spur", "Bentayga", "Bentayga Speed", "Mulsanne", "Bacalar", "Batur", "Continental Supersports"],
    "Rolls-Royce": ["Ghost", "Wraith", "Dawn", "Phantom", "Cullinan", "Spectre", "Black Badge Ghost", "Black Badge Cullinan", "Boat Tail"],
    "Maserati": ["Ghibli", "Quattroporte", "Levante", "Grecale", "GranTurismo", "GranCabrio", "MC20", "MC20 Cielo", "MC12"],
    "Jaguar": ["XE P300", "XF P300", "F-Type", "F-Pace SVR", "E-Pace", "I-Pace", "XJ", "XK-R", "XJR"],
    "Lotus": ["Emira", "Evora GT", "Exige Cup 430", "Elise Cup 250", "Eletre R", "Emeya", "Esprit V8", "Elise S", "Evora GT430"],
    "Alfa Romeo": ["Giulia", "Giulia Veloce", "Giulia Quadrifoglio", "Stelvio", "Stelvio Quadrifoglio", "4C", "4C Spider", "8C Competizione", "33 Stradale"],
    "Lexus": ["IS 500", "RC F", "LC 500", "LC 500 Convertible", "LS 500", "LX 600", "GX 550", "LFA", "RC 350"],
    "Toyota": ["GR86", "GR Supra", "GR Yaris", "GR Corolla", "Camry TRD", "Tacoma TRD Pro", "Tundra TRD Pro", "Land Cruiser", "Century"],
    "Nissan": ["370Z", "400Z", "GT-R", "GT-R Nismo", "Silvia S15", "Skyline R34", "Z Nismo", "Juke Nismo", "Z Proto"],
    "Honda": ["Civic Si", "Civic Type R", "Integra Type S", "NSX", "S2000", "Prelude", "Accord Sport", "CR-V Hybrid", "NSX Type S"],
    "Mazda": ["MX-5", "MX-5 RF", "Mazda3 Turbo", "Mazda6", "CX-5 Turbo", "CX-50", "CX-60", "RX-7 FD", "RX-8"],
    "Subaru": ["BRZ", "WRX", "WRX STI", "Levorg", "Forester XT", "Outback XT", "Impreza WRX", "Impreza STI", "SVX"],
    "Mitsubishi": ["Lancer Evolution VIII", "Lancer Evolution IX", "Lancer Evolution X", "Eclipse", "Eclipse Cross", "Outlander", "Pajero", "3000GT", "Galant VR-4"],
    "Ford": ["Mustang GT", "Mustang Dark Horse", "GT", "Focus RS", "Fiesta ST", "F-150 Raptor", "Bronco Raptor", "Ranger Raptor", "GT40"],
    "Chevrolet": ["Camaro SS", "Camaro ZL1", "Corvette C8", "Corvette Z06", "Corvette ZR1", "Silverado ZR2", "Tahoe RST", "Impala SS", "Chevelle SS"],
    "Dodge": ["Charger R/T", "Charger Hellcat", "Challenger R/T", "Challenger Hellcat", "Challenger Demon", "Viper GTS", "Durango SRT", "Hornet R/T", "Dart GT"],
    "Jeep": ["Wrangler Rubicon", "Grand Cherokee SRT", "Grand Cherokee Trackhawk", "Gladiator Rubicon", "Wagoneer", "Renegade Trailhawk", "Cherokee Trailhawk", "Compass Trailhawk", "Avenger"],
    "Cadillac": ["CT4-V", "CT5-V", "CT5-V Blackwing", "Escalade", "Escalade-V", "Lyriq", "CTS-V", "ATS-V", "XLR-V"],
    "Tesla": ["Model 3", "Model 3 Performance", "Model S", "Model S Plaid", "Model X", "Model X Plaid", "Model Y", "Model Y Performance", "Roadster"],
    "Koenigsegg": ["CCX", "CCR", "Agera", "Agera RS", "Regera", "Jesko", "Jesko Absolut", "Gemera", "One:1"],
    "Pagani": ["Zonda C12", "Zonda F", "Zonda Cinque", "Zonda R", "Huayra", "Huayra BC", "Huayra Roadster", "Utopia", "Huayra Imola"],
    "Bugatti": ["Veyron", "Veyron Super Sport", "Chiron", "Chiron Sport", "Chiron Pur Sport", "Chiron Super Sport", "Divo", "Centodieci", "Mistral"],
    "Rimac": ["Concept One", "Concept S", "Nevera", "Nevera R", "C_Two", "Verne", "Nevera Time Attack", "Nevera Track", "Nevera Founder"],
    "Shelby": ["Cobra 427", "Cobra Daytona", "GT350", "GT500", "Super Snake", "Series 1", "GT500KR", "Cobra Super Snake", "GT350R"],
    "Gordon Murray": ["T.33", "T.33 Spider", "T.50", "T.50s Niki Lauda", "T.50 Track", "T.33 V12", "T.50 Cosworth", "T.50 Road", "T.50 Special"],
}

CAR_YEARS = {'Volkswagen': {'Golf GTI': 2020,
                'Golf R': 2022,
                'Passat R-Line': 2020,
                'Arteon R': 2020,
                'Polo GTI': 2021,
                'T-Roc R': 2019,
                'Tiguan R': 2020,
                'Touareg R': 2020,
                'Scirocco R': 2014},
 'BMW': {'M2': 2023,
         'M3': 2021,
         'M4': 2021,
         'M5': 2021,
         'M8': 2020,
         'X3 M': 2019,
         'X5 M': 2019,
         'Z4 M40i': 2019,
         'i8': 2014},
 'Mercedes-Benz': {'A45 AMG': 2019,
                   'C63 AMG': 2018,
                   'E63 AMG': 2021,
                   'S63 AMG': 2021,
                   'AMG GT': 2015,
                   'GT 63 S': 2018,
                   'G63 AMG': 2018,
                   'SL63 AMG': 2022,
                   'EQS 53': 2021},
 'Audi': {'S3': 2020,
          'S4': 2020,
          'S5': 2020,
          'RS3': 2021,
          'RS4': 2018,
          'RS5': 2017,
          'RS6 Avant': 2020,
          'RS7': 2019,
          'R8 V10': 2015},
 'Porsche': {'718 Cayman': 2016,
             '718 Boxster': 2016,
             '911 Carrera': 2020,
             '911 Turbo S': 2020,
             '911 GT3': 2021,
             '911 GT3 RS': 2022,
             'Taycan Turbo S': 2019,
             'Panamera Turbo S': 2020,
             'Cayenne Turbo GT': 2021},
 'Ferrari': {'Roma': 2019,
             'Portofino M': 2020,
             'F8 Tributo': 2019,
             'F8 Spider': 2019,
             '296 GTB': 2021,
             '296 GTS': 2022,
             '812 Superfast': 2017,
             'SF90 Stradale': 2019,
             'LaFerrari': 2013},
 'Lamborghini': {'Huracan EVO': 2019,
                 'Huracan STO': 2020,
                 'Huracan Tecnica': 2022,
                 'Urus': 2018,
                 'Urus Performante': 2022,
                 'Revuelto': 2023,
                 'Aventador SVJ': 2018,
                 'Aventador S': 2016,
                 'Sian': 2019},
 'McLaren': {'570S': 2015,
             '600LT': 2018,
             '720S': 2017,
             '765LT': 2020,
             'Artura': 2021,
             'GT': 2019,
             '750S': 2023,
             'Senna': 2017,
             'Speedtail': 2019},
 'Aston Martin': {'Vantage': 2018,
                  'DB11': 2016,
                  'DB12': 2023,
                  'DBS': 2018,
                  'Vanquish': 2012,
                  'Valkyrie': 2021,
                  'Valhalla': 2024,
                  'Rapide S': 2013,
                  'One-77': 2009},
 'Bentley': {'Continental GT': 2018,
             'Continental GTC': 2019,
             'Flying Spur': 2019,
             'Bentayga': 2015,
             'Bentayga Speed': 2019,
             'Mulsanne': 2010,
             'Bacalar': 2020,
             'Batur': 2022,
             'Continental Supersports': 2017},
 'Rolls-Royce': {'Ghost': 2020,
                 'Wraith': 2013,
                 'Dawn': 2015,
                 'Phantom': 2017,
                 'Cullinan': 2018,
                 'Spectre': 2023,
                 'Black Badge Ghost': 2021,
                 'Black Badge Cullinan': 2019,
                 'Boat Tail': 2021},
 'Maserati': {'Ghibli': 2013,
              'Quattroporte': 2013,
              'Levante': 2016,
              'Grecale': 2022,
              'GranTurismo': 2023,
              'GranCabrio': 2010,
              'MC20': 2021,
              'MC20 Cielo': 2022,
              'MC12': 2004},
 'Jaguar': {'XE P300': 2017,
            'XF P300': 2017,
            'F-Type': 2013,
            'F-Pace SVR': 2018,
            'E-Pace': 2017,
            'I-Pace': 2018,
            'XJ': 2010,
            'XK-R': 2006,
            'XJR': 2013},
 'Lotus': {'Emira': 2022,
           'Evora GT': 2019,
           'Exige Cup 430': 2017,
           'Elise Cup 250': 2016,
           'Eletre R': 2022,
           'Emeya': 2024,
           'Esprit V8': 1996,
           'Elise S': 2010,
           'Evora GT430': 2017},
 'Alfa Romeo': {'Giulia': 2016,
                'Giulia Veloce': 2016,
                'Giulia Quadrifoglio': 2016,
                'Stelvio': 2016,
                'Stelvio Quadrifoglio': 2017,
                '4C': 2013,
                '4C Spider': 2015,
                '8C Competizione': 2007,
                '33 Stradale': 2023},
 'Lexus': {'IS 500': 2021,
           'RC F': 2014,
           'LC 500': 2016,
           'LC 500 Convertible': 2020,
           'LS 500': 2017,
           'LX 600': 2021,
           'GX 550': 2023,
           'LFA': 2010,
           'RC 350': 2014},
 'Toyota': {'GR86': 2021,
            'GR Supra': 2019,
            'GR Yaris': 2020,
            'GR Corolla': 2022,
            'Camry TRD': 2020,
            'Tacoma TRD Pro': 2015,
            'Tundra TRD Pro': 2014,
            'Land Cruiser': 2021,
            'Century': 2018},
 'Nissan': {'370Z': 2008,
            '400Z': 2021,
            'GT-R': 2007,
            'GT-R Nismo': 2014,
            'Silvia S15': 1999,
            'Skyline R34': 1999,
            'Z Nismo': 2023,
            'Juke Nismo': 2013,
            'Z Proto': 2020},
 'Honda': {'Civic Si': 2017,
           'Civic Type R': 2017,
           'Integra Type S': 2023,
           'NSX': 2016,
           'S2000': 1999,
           'Prelude': 1978,
           'Accord Sport': 2018,
           'CR-V Hybrid': 2019,
           'NSX Type S': 2021},
 'Mazda': {'MX-5': 2015,
           'MX-5 RF': 2016,
           'Mazda3 Turbo': 2020,
           'Mazda6': 2012,
           'CX-5 Turbo': 2019,
           'CX-50': 2022,
           'CX-60': 2022,
           'RX-7 FD': 1992,
           'RX-8': 2003},
 'Subaru': {'BRZ': 2021,
            'WRX': 2021,
            'WRX STI': 2014,
            'Levorg': 2014,
            'Forester XT': 2013,
            'Outback XT': 2019,
            'Impreza WRX': 2007,
            'Impreza STI': 2007,
            'SVX': 1991},
 'Mitsubishi': {'Lancer Evolution VIII': 2003,
                'Lancer Evolution IX': 2005,
                'Lancer Evolution X': 2007,
                'Eclipse': 1999,
                'Eclipse Cross': 2017,
                'Outlander': 2021,
                'Pajero': 2006,
                '3000GT': 1990,
                'Galant VR-4': 1987},
 'Ford': {'Mustang GT': 2015,
          'Mustang Dark Horse': 2023,
          'GT': 2017,
          'Focus RS': 2015,
          'Fiesta ST': 2013,
          'F-150 Raptor': 2017,
          'Bronco Raptor': 2022,
          'Ranger Raptor': 2018,
          'GT40': 1966},
 'Chevrolet': {'Camaro SS': 2016,
               'Camaro ZL1': 2016,
               'Corvette C8': 2019,
               'Corvette Z06': 2022,
               'Corvette ZR1': 2025,
               'Silverado ZR2': 2021,
               'Tahoe RST': 2021,
               'Impala SS': 1994,
               'Chevelle SS': 1964},
 'Dodge': {'Charger R/T': 2006,
           'Charger Hellcat': 2014,
           'Challenger R/T': 2008,
           'Challenger Hellcat': 2014,
           'Challenger Demon': 2017,
           'Viper GTS': 1996,
           'Durango SRT': 2017,
           'Hornet R/T': 2023,
           'Dart GT': 2013},
 'Jeep': {'Wrangler Rubicon': 2003,
          'Grand Cherokee SRT': 2012,
          'Grand Cherokee Trackhawk': 2017,
          'Gladiator Rubicon': 2019,
          'Wagoneer': 2021,
          'Renegade Trailhawk': 2014,
          'Cherokee Trailhawk': 2014,
          'Compass Trailhawk': 2017,
          'Avenger': 2023},
 'Cadillac': {'CT4-V': 2020,
              'CT5-V': 2019,
              'CT5-V Blackwing': 2021,
              'Escalade': 2020,
              'Escalade-V': 2022,
              'Lyriq': 2022,
              'CTS-V': 2015,
              'ATS-V': 2015,
              'XLR-V': 2005},
 'Tesla': {'Model 3': 2017,
           'Model 3 Performance': 2018,
           'Model S': 2012,
           'Model S Plaid': 2021,
           'Model X': 2015,
           'Model X Plaid': 2021,
           'Model Y': 2019,
           'Model Y Performance': 2020,
           'Roadster': 2008},
 'Koenigsegg': {'CCX': 2006,
                'CCR': 2004,
                'Agera': 2010,
                'Agera RS': 2015,
                'Regera': 2015,
                'Jesko': 2019,
                'Jesko Absolut': 2020,
                'Gemera': 2020,
                'One:1': 2014},
 'Pagani': {'Zonda C12': 1999,
            'Zonda F': 2005,
            'Zonda Cinque': 2009,
            'Zonda R': 2007,
            'Huayra': 2011,
            'Huayra BC': 2016,
            'Huayra Roadster': 2017,
            'Utopia': 2022,
            'Huayra Imola': 2020},
 'Bugatti': {'Veyron': 2005,
             'Veyron Super Sport': 2010,
             'Chiron': 2016,
             'Chiron Sport': 2018,
             'Chiron Pur Sport': 2020,
             'Chiron Super Sport': 2021,
             'Divo': 2018,
             'Centodieci': 2019,
             'Mistral': 2022},
 'Rimac': {'Concept One': 2013,
           'Concept S': 2016,
           'Nevera': 2021,
           'Nevera R': 2024,
           'C_Two': 2018,
           'Verne': 2024,
           'Nevera Time Attack': 2024,
           'Nevera Track': 2023,
           'Nevera Founder': 2021},
 'Shelby': {'Cobra 427': 1965,
            'Cobra Daytona': 1964,
            'GT350': 1965,
            'GT500': 1967,
            'Super Snake': 1967,
            'Series 1': 1999,
            'GT500KR': 2008,
            'Cobra Super Snake': 1967,
            'GT350R': 1965},
 'Gordon Murray': {'T.33': 2022,
                   'T.33 Spider': 2025,
                   'T.50': 2020,
                   'T.50s Niki Lauda': 2021,
                   'T.50 Track': 2023,
                   'T.33 V12': 2022,
                   'T.50 Cosworth': 2022,
                   'T.50 Road': 2022,
                   'T.50 Special': 2024}}

RARITY_ORDER = list(RARITIES.keys())

# 306 машин: 136 Common, 73 Uncommon, 49 Rare, 25 Epic,
# 15 Legendary, 6 Exclusive, 2 Secret.
RARITY_COUNTS = {
    "Common": 136,
    "Uncommon": 73,
    "Rare": 49,
    "Epic": 25,
    "Legendary": 15,
    "Exclusive": 6,
    "Secret": 2,
}

BASE_PRICES = {
    "Common": 600_000,
    "Uncommon": 1_500_000,
    "Rare": 4_000_000,
    "Epic": 10_000_000,
    "Legendary": 30_000_000,
    "Exclusive": 90_000_000,
    "Secret": 300_000_000,
}


def build_cars():
    names = [f"{brand} {model}" for brand, models in BRAND_MODELS.items() for model in models]
    total = len(names)

    # Используем только реально существующие машины.
    # Ничего добавлять не нужно: сейчас в игре 306 автомобилей.
    cars = []
    rarity_limits = []
    current = 0
    for rarity in RARITY_ORDER:
        current += RARITY_COUNTS[rarity]
        rarity_limits.append((current, rarity))

    for index, name in enumerate(names):
        # Определяем редкость по позиции машины.
        rarity = RARITY_ORDER[-1]
        for limit, r in rarity_limits:
            if index < limit:
                rarity = r
                break

        multiplier = {
            "Common": (0.8, 1.2),
            "Uncommon": (0.9, 1.25),
            "Rare": (1.0, 1.35),
            "Epic": (1.1, 1.45),
            "Legendary": (1.2, 1.6),
            "Exclusive": (1.35, 1.8),
            "Secret": (1.5, 2.0),
        }[rarity]
        power = int(random.randint(90, 700) * random.uniform(*multiplier))
        price = int(BASE_PRICES[rarity] * random.uniform(0.85, 1.25))
        cars.append({
            "id": index + 1,
            "name": name,
            "year": next((CAR_YEARS[b][m] for b, models in BRAND_MODELS.items() for m in models if f"{b} {m}" == name), 2020),
            "rarity": rarity,
            "power": power,
            "price": price,
        })

    assert len(cars) == total == 306, f"Должно быть 306 машин, получено {len(cars)}"
    return cars


CARS = build_cars()
CARS_BY_ID = {car["id"]: car for car in CARS}
CARS_BY_RARITY = {rarity: [c for c in CARS if c["rarity"] == rarity] for rarity in RARITY_ORDER}

# =========================================================
# DATABASE / V2
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 5000000,
                cases_opened INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                last_case_opened REAL NOT NULL DEFAULT 0,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                referrer_id INTEGER,
                referrals INTEGER NOT NULL DEFAULT 0,
                referral_earned INTEGER NOT NULL DEFAULT 0,
                daily_last REAL NOT NULL DEFAULT 0,
                daily_streak INTEGER NOT NULL DEFAULT 0,
                quest_cases_claimed INTEGER NOT NULL DEFAULT 0,
                quest_rare_claimed INTEGER NOT NULL DEFAULT 0,
                quest_ref_claimed INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS garage (
                user_id INTEGER NOT NULL,
                car_id INTEGER NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, car_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS containers (
                user_id INTEGER NOT NULL,
                container_id TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, container_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auction (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                car_id INTEGER NOT NULL,
                current_bid INTEGER NOT NULL DEFAULT 0,
                bidder_id INTEGER,
                ends_at REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                power INTEGER NOT NULL,
                price INTEGER NOT NULL,
                rarity TEXT NOT NULL,
                image_file_id TEXT DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                created_by INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward INTEGER NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 0,
                uses INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_used (
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                used_at REAL NOT NULL,
                PRIMARY KEY (user_id, code)
            )
        """)

        # Safe migrations for databases created by the previous version.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        migrations = {
            "username": "ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''",
            "first_name": "ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT ''",
            "referrer_id": "ALTER TABLE users ADD COLUMN referrer_id INTEGER",
            "referrals": "ALTER TABLE users ADD COLUMN referrals INTEGER NOT NULL DEFAULT 0",
            "referral_earned": "ALTER TABLE users ADD COLUMN referral_earned INTEGER NOT NULL DEFAULT 0",
            "daily_last": "ALTER TABLE users ADD COLUMN daily_last REAL NOT NULL DEFAULT 0",
            "daily_streak": "ALTER TABLE users ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0",
            "quest_cases_claimed": "ALTER TABLE users ADD COLUMN quest_cases_claimed INTEGER NOT NULL DEFAULT 0",
            "quest_rare_claimed": "ALTER TABLE users ADD COLUMN quest_rare_claimed INTEGER NOT NULL DEFAULT 0",
            "quest_ref_claimed": "ALTER TABLE users ADD COLUMN quest_ref_claimed INTEGER NOT NULL DEFAULT 0",
        }
        for col, sql in migrations.items():
            if col not in columns:
                conn.execute(sql)

        auction_columns = {row[1] for row in conn.execute("PRAGMA table_info(auction)").fetchall()}
        if "created_at" not in auction_columns:
            conn.execute("ALTER TABLE auction ADD COLUMN created_at REAL NOT NULL DEFAULT 0")

        # Starter promo codes. They are created only once and can be disabled by admin.
        conn.execute("INSERT OR IGNORE INTO promo_codes(code, reward, max_uses) VALUES ('ZONA100', 100000, 0)")
        conn.execute("INSERT OR IGNORE INTO promo_codes(code, reward, max_uses) VALUES ('START500', 500000, 0)")


def load_custom_cars():
    """Загружает машины, добавленные создателем, из SQLite."""
    global CARS, CARS_BY_ID, CARS_BY_RARITY
    with db() as conn:
        rows = conn.execute("SELECT * FROM cars ORDER BY id").fetchall()
    custom = []
    for row in rows:
        if row["rarity"] not in RARITIES:
            continue
        custom.append({
            "id": int(row["id"]),
            "name": row["name"],
            "year": int(row["year"]),
            "rarity": row["rarity"],
            "power": int(row["power"]),
            "price": int(row["price"]),
            "image_file_id": row["image_file_id"] or "",
        })
    # Сначала базовые 306 машин, затем пользовательские.
    CARS = build_cars() + custom
    CARS_BY_ID = {car["id"]: car for car in CARS}
    CARS_BY_RARITY = {rarity: [c for c in CARS if c["rarity"] == rarity] for rarity in RARITY_ORDER}


def next_custom_car_id():
    with db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(id), 999) FROM cars").fetchone()
    return max(1000, int(row[0]) + 1)


def save_custom_car(name, year, power, price, rarity, image_file_id, created_by):
    car_id = next_custom_car_id()
    with db() as conn:
        conn.execute("""
            INSERT INTO cars(id,name,year,power,price,rarity,image_file_id,created_at,created_by)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (car_id, name, year, power, price, rarity, image_file_id, time.time(), created_by))
    load_custom_cars()
    return CARS_BY_ID[car_id]


def find_car_admin(value):
    value = value.strip()
    if value.isdigit() and int(value) in CARS_BY_ID:
        return CARS_BY_ID[int(value)]
    low = value.casefold()
    exact = [c for c in CARS if c["name"].casefold() == low]
    if exact:
        return exact[0]
    partial = [c for c in CARS if low in c["name"].casefold()]
    return partial[0] if partial else None


def car_caption(car, amount=1, include_sell=True):
    r = RARITIES[car["rarity"]]
    text = (
        f'{r["emoji"]} <b>{escape(car["name"])}</b>\n\n'
        f'⭐ Редкость: <b>{escape(car["rarity"])}</b>\n'
        f'📅 Год выпуска: <b>{car["year"]}</b>\n'
        f'⚡ Мощность: <b>{car["power"]} л.с.</b>\n'
        f'💎 Стоимость: <b>{money(car["price"])}</b>\n'
        f'📦 В коллекции: <b>{amount} шт.</b>'
    )
    if include_sell:
        text += f'\n💵 Продажа одной: <b>{money(int(car["price"] * r["sell"]))}</b>'
    return text




def ensure_user(user_id, username=None, first_name=None):
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
        if username is not None or first_name is not None:
            conn.execute(
                "UPDATE users SET username=COALESCE(?, username), first_name=COALESCE(?, first_name) WHERE user_id=?",
                (username, first_name, user_id),
            )


def get_user(user_id):
    ensure_user(user_id)
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def add_balance(user_id, amount):
    ensure_user(user_id)
    with db() as conn:
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (int(amount), user_id))


def add_xp(user_id, amount):
    ensure_user(user_id)
    with db() as conn:
        conn.execute("UPDATE users SET xp=xp+? WHERE user_id=?", (int(amount), user_id))


def add_car(user_id, car_id, amount=1):
    with db() as conn:
        conn.execute("""
            INSERT INTO garage(user_id, car_id, amount) VALUES (?, ?, ?)
            ON CONFLICT(user_id, car_id) DO UPDATE SET amount=amount+excluded.amount
        """, (user_id, car_id, amount))


def get_garage(user_id, rarity=None):
    with db() as conn:
        rows = conn.execute(
            "SELECT car_id, amount FROM garage WHERE user_id=? AND amount>0", (user_id,)
        ).fetchall()
    result = []
    for row in rows:
        car = CARS_BY_ID.get(row["car_id"])
        if car and (rarity is None or car["rarity"] == rarity):
            result.append((car, row["amount"]))
    result.sort(key=lambda x: (RARITY_ORDER.index(x[0]["rarity"]), x[0]["name"]))
    return result


def garage_summary(user_id):
    items = get_garage(user_id)
    return len(items), sum(amount for _, amount in items)


def get_container_amount(user_id, container_id):
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM containers WHERE user_id=? AND container_id=?",
            (user_id, container_id),
        ).fetchone()
    return row["amount"] if row else 0


def add_container(user_id, container_id, amount=1):
    with db() as conn:
        conn.execute("""
            INSERT INTO containers(user_id, container_id, amount) VALUES (?, ?, ?)
            ON CONFLICT(user_id, container_id) DO UPDATE SET amount=amount+excluded.amount
        """, (user_id, container_id, amount))


def remove_container(user_id, container_id, amount=1):
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM containers WHERE user_id=? AND container_id=?",
            (user_id, container_id),
        ).fetchone()
        if not row or row["amount"] < amount:
            return False
        conn.execute(
            "UPDATE containers SET amount=amount-? WHERE user_id=? AND container_id=?",
            (amount, user_id, container_id),
        )
        conn.execute("DELETE FROM containers WHERE amount<=0")
    return True


def sell_car(user_id, car_id, amount=1):
    car = CARS_BY_ID.get(car_id)
    if not car or amount < 1:
        return 0
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?", (user_id, car_id)
        ).fetchone()
        if not row or row["amount"] < amount:
            return 0
        payout = int(car["price"] * RARITIES[car["rarity"]]["sell"]) * amount
        conn.execute("UPDATE garage SET amount=amount-? WHERE user_id=? AND car_id=?", (amount, user_id, car_id))
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (payout, user_id))
        conn.execute("DELETE FROM garage WHERE amount<=0")
    return payout


def money(value):
    return f"{int(value):,}".replace(",", " ") + "₽"


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"


def choose_car():
    rarity = random.choices(RARITY_ORDER, weights=[RARITIES[r]["chance"] for r in RARITY_ORDER], k=1)[0]
    return random.choice(CARS_BY_RARITY[rarity])


def choose_container_car(container_id):
    c = CONTAINERS[container_id]
    rarity = random.choice(c["rarities"])
    return random.choice(CARS_BY_RARITY[rarity])

# =========================================================
# AUCTION V2 — ставка резервирует деньги сразу
# =========================================================

def get_auction():
    with db() as conn:
        return conn.execute("SELECT * FROM auction WHERE id=1").fetchone()


def refund_auction_bid(conn, auction):
    if auction and auction["bidder_id"] and auction["current_bid"] > 0:
        conn.execute(
            "UPDATE users SET balance=balance+? WHERE user_id=?",
            (auction["current_bid"], auction["bidder_id"]),
        )


def start_new_auction():
    car = random.choice(CARS_BY_RARITY["Exclusive"])
    with db() as conn:
        old = conn.execute("SELECT * FROM auction WHERE id=1").fetchone()
        if old and old["active"] and old["bidder_id"] and old["current_bid"]:
            refund_auction_bid(conn, old)
        now = time.time()
        conn.execute("""
            INSERT INTO auction(id, car_id, current_bid, bidder_id, ends_at, created_at, active)
            VALUES (1, ?, 0, NULL, 0, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                car_id=excluded.car_id, current_bid=0, bidder_id=NULL,
                ends_at=0, created_at=excluded.created_at, active=1
        """, (car["id"], now))
    return car


def auction_text(auction):
    if not auction or not auction["active"]:
        return "🔴 <b>ЭКСКЛЮЗИВНЫЙ АУКЦИОН</b>\n\nЛот сейчас неактивен. Новый появится автоматически."
    car = CARS_BY_ID.get(auction["car_id"])
    if not car:
        return "🔴 Лот не найден."
    bid = auction["current_bid"]
    if auction["bidder_id"] and auction["ends_at"] > time.time():
        timer = f"⏳ Осталось: <b>{fmt_time(auction['ends_at']-time.time())}</b>"
    else:
        timer = "⏳ Ставок нет — сделай первую ставку."
    next_bid = AUCTION_MIN_BID if not bid else bid + AUCTION_BID_STEP
    bidder = "—"
    if auction["bidder_id"]:
        u = get_user(auction["bidder_id"])
        bidder = "@" + u["username"] if u["username"] else f"ID {auction['bidder_id']}"
    return (
        "🔴 <b>ЭКСКЛЮЗИВНЫЙ АУКЦИОН</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🚘 <b>{escape(car['name'])}</b>\n"
        f"📅 {car['year']} год  •  ⚡ {car['power']} л.с.\n"
        f"💎 Цена машины: <b>{money(car['price'])}</b>\n\n"
        f"💰 Ставка: <b>{money(bid) if bid else 'нет ставок'}</b>\n"
        f"👤 Лидер: <b>{escape(bidder)}</b>\n"
        f"⬆️ Следующая: <b>{money(next_bid)}</b>\n"
        f"{timer}\n\n"
        "💳 Деньги ставки резервируются сразу и возвращаются предыдущему лидеру."
    )


def auction_keyboard(auction):
    kb = InlineKeyboardBuilder()
    if auction and auction["active"]:
        bid = auction["current_bid"]
        next_bid = AUCTION_MIN_BID if not bid else bid + AUCTION_BID_STEP
        kb.button(text=f"💰 Ставка {money(next_bid)}", callback_data="auction:bid")
    kb.button(text="🔄 Обновить", callback_data="auction:show")
    kb.button(text="⬅️ Контейнеры", callback_data="containers:list")
    kb.adjust(1)
    return kb.as_markup()


def finish_auction():
    auction = get_auction()
    if not auction or not auction["active"] or not auction["bidder_id"] or auction["ends_at"] > time.time():
        return False
    car = CARS_BY_ID.get(auction["car_id"])
    if not car:
        return False
    winner_id = auction["bidder_id"]
    bid = auction["current_bid"]
    with db() as conn:
        conn.execute("UPDATE auction SET active=0, created_at=? WHERE id=1", (time.time(),))
    add_car(winner_id, car["id"])
    add_xp(winner_id, 300)
    return winner_id, car, bid


async def auction_loop(bot):
    while True:
        try:
            result = finish_auction()
            if result:
                winner_id, car, bid = result
                try:
                    winner_text = (
                        "🏆 <b>ТЫ ПОБЕДИЛ В АУКЦИОНЕ!</b>\n\n"
                        f"🔴 {escape(car['name'])}\n💰 Ставка: <b>{money(bid)}</b>\n"
                        "🚘 Машина добавлена в гараж!"
                    )
                    if car.get("image_file_id"):
                        await bot.send_photo(winner_id, car["image_file_id"], caption=winner_text, parse_mode="HTML")
                    else:
                        await bot.send_message(winner_id, winner_text, parse_mode="HTML")
                except Exception:
                    pass
            auction = get_auction()
            now = time.time()
            if not auction:
                start_new_auction()
            elif not auction["active"] and now - auction["created_at"] >= AUCTION_INTERVAL:
                start_new_auction()
            elif auction["active"] and now - auction["created_at"] >= AUCTION_INTERVAL and not auction["bidder_id"]:
                start_new_auction()
        except Exception:
            logging.exception("Ошибка аукциона")
        await asyncio.sleep(1)

# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    kb = ReplyKeyboardBuilder()
    for text in [
        "🚘 Открыть авто", "🏠 Гараж", "📦 Контейнеры", "👤 Профиль",
        "📝 Квесты", "🏆 Сезон", "🎁 Промокод", "👥 Реферальная ссылка",
        "🎁 Бонус дня", "🏆 Лидеры",
    ]:
        kb.button(text=text)
    kb.adjust(2, 2, 2, 2, 2)
    return kb.as_markup(resize_keyboard=True)


def case_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 ОТКРЫТЬ КЕЙС", callback_data="open_case")
    kb.button(text="📊 Редкости", callback_data="rarities")
    kb.button(text="⬅️ Меню", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def containers_tabs(active="containers"):
    kb = InlineKeyboardBuilder()
    kb.button(text=("✅ 📦 Контейнеры" if active == "containers" else "📦 Контейнеры"), callback_data="containers:list")
    kb.button(text=("✅ 🔴 Аукцион" if active == "exclusive" else "🔴 Аукцион"), callback_data="containers:exclusive")
    kb.adjust(2)
    return kb


def containers_keyboard(user_id):
    kb = containers_tabs("containers")
    for cid, c in CONTAINERS.items():
        kb.button(text=f"{c['emoji']} {c['name']} • {money(c['price'])} • ×{get_container_amount(user_id, cid)}", callback_data=f"container:info:{cid}")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def container_info_keyboard(container_id, user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Купить 1", callback_data=f"container:buy:{container_id}")
    if get_container_amount(user_id, container_id) > 0:
        kb.button(text="🎁 Открыть 1", callback_data=f"container:open:{container_id}")
    kb.button(text="⬅️ Контейнеры", callback_data="containers:list")
    kb.adjust(1)
    return kb.as_markup()


def garage_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Все машины", callback_data="garage:all")
    for rarity in RARITY_ORDER:
        kb.button(text=f"{RARITIES[rarity]['emoji']} {rarity}", callback_data=f"garage:{rarity}")
    kb.button(text="⬅️ Меню", callback_data="back_menu")
    kb.adjust(2)
    return kb.as_markup()


def garage_page_keyboard(items, page, rarity):
    kb = InlineKeyboardBuilder()
    start = page * 8
    for car, amount in items[start:start+8]:
        kb.button(text=f"{RARITIES[car['rarity']]['emoji']} {car['name']} ×{amount}", callback_data=f"car:{car['id']}")
    kb.adjust(1)
    total_pages = max(1, (len(items)+7)//8)
    if total_pages > 1:
        if page > 0:
            kb.button(text="⬅️", callback_data=f"gpage:{rarity or 'all'}:{page-1}")
        kb.button(text=f"{page+1}/{total_pages}", callback_data="noop")
        if page+1 < total_pages:
            kb.button(text="➡️", callback_data=f"gpage:{rarity or 'all'}:{page+1}")
    kb.button(text="🔎 Фильтр", callback_data="garage_filters")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def car_keyboard(car_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💵 Продать 1", callback_data=f"sell:{car_id}:1")
    kb.button(text="💵 Продать всё", callback_data=f"sellall:{car_id}")
    kb.button(text="⬅️ В гараж", callback_data="garage:all")
    kb.adjust(2, 1)
    return kb.as_markup()


def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin:stats")
    kb.button(text="🚘 Выдать машину", callback_data="admin:give_car")
    kb.button(text="➕ Добавить машину", callback_data="admin:add_car")
    kb.button(text="📋 Мои добавленные машины", callback_data="admin:custom_cars")
    kb.button(text="🔴 Аукцион", callback_data="admin:auction")
    kb.button(text="🚘 Новый аукцион", callback_data="admin:new_auction")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

# =========================================================
# VIEWS
# =========================================================

def rarity_text():
    lines = ["⭐ <b>РЕДКОСТИ И ШАНСЫ</b>", ""]
    for rarity in RARITY_ORDER:
        r = RARITIES[rarity]
        lines.append(f"{r['emoji']} <b>{rarity}</b> — {r['chance']}% • {len(CARS_BY_RARITY[rarity])} машин")
    return "\n".join(lines)


async def show_garage_page(message, user_id, rarity, page=0, edit=False):
    items = get_garage(user_id, None if rarity == "all" else rarity)
    if not items:
        text = "🏠 <b>ГАРАЖ</b>\n\nЗдесь пока пусто. Открой кейс или контейнер!"
        if edit:
            await message.edit_text(text, reply_markup=garage_keyboard(), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=garage_keyboard(), parse_mode="HTML")
        return
    total_pages = max(1, (len(items)+7)//8)
    page = max(0, min(page, total_pages-1))
    text = f"🏠 <b>ГАРАЖ</b>\n\n🚘 Машин: <b>{len(items)}</b> уникальных\n📄 Страница: <b>{page+1}/{total_pages}</b>\n\nВыбери автомобиль:"
    markup = garage_page_keyboard(items, page, None if rarity == "all" else rarity)
    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

# =========================================================
# START / PROFILE
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    parts = (message.text or "").split(maxsplit=1)
    referral_id = None
    if len(parts) == 2 and parts[1].strip().isdigit():
        referral_id = int(parts[1].strip())
    if referral_id and referral_id != user_id:
        with db() as conn:
            me = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,)).fetchone()
            ref = conn.execute("SELECT user_id FROM users WHERE user_id=?", (referral_id,)).fetchone()
            if me and ref and me["referrer_id"] is None:
                conn.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referral_id, user_id))
                conn.execute("UPDATE users SET referrals=referrals+1, referral_earned=referral_earned+250000, balance=balance+250000 WHERE user_id=?", (referral_id,))
    user = get_user(user_id)
    unique, total = garage_summary(user_id)
    await message.answer(
        "🚘 <b>Добро пожаловать в Zona CarCase V2!</b>\n\n"
        "🎁 Кейсы  •  📦 контейнеры  •  🔴 аукцион\n"
        "🏠 Гараж  •  🏆 сезон  •  📝 квесты\n\n"
        f"💰 Баланс: <b>{money(user['balance'])}</b>\n"
        f"🚘 Коллекция: <b>{unique}{len(CARS)}</b>\n"
        f"📦 Всего машин: <b>{total}</b>",
        reply_markup=main_keyboard(), parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(message: Message):
    user = get_user(message.from_user.id)
    unique, total = garage_summary(message.from_user.id)
    level = user["xp"] // 1000 + 1
    current_xp = user["xp"] % 1000
    progress = int(current_xp / 1000 * 10)
    xp_bar = "🟩" * progress + "⬜" * (10-progress)
    await message.answer(
        "👤 <b>ТВОЙ ПРОФИЛЬ</b>\n━━━━━━━━━━━━━━\n\n"
        f"💰 Баланс: <b>{money(user['balance'])}</b>\n"
        f"⭐ Уровень: <b>{level}</b>\n{xp_bar} <b>{current_xp}/1000 XP</b>\n\n"
        f"🚘 Уникальных: <b>{unique}{len(CARS)}</b>\n📦 Всего машин: <b>{total}</b>\n"
        f"🎁 Открыто кейсов: <b>{user['cases_opened']}</b>\n"
        f"👥 Рефералов: <b>{user['referrals']}</b>\n"
        f"💸 Заработано с рефералов: <b>{money(user['referral_earned'])}</b>",
        parse_mode="HTML"
    )

# =========================================================
# CASES
# =========================================================

@dp.message(lambda m: m.text == "🚘 Открыть авто")
async def open_auto(message: Message):
    await message.answer(
        "🎁 <b>COMMON CASE</b>\n\n"
        f"💰 Цена: <b>{money(CASE_PRICE)}</b>\n⏳ КД: <b>3 часа</b>\n\n"
        "⭐ Шансы:\n" + "\n".join(
            f"{RARITIES[r]['emoji']} {r} — {RARITIES[r]['chance']}%" for r in RARITY_ORDER
        ) + "\n\nНажми кнопку ниже:",
        reply_markup=case_keyboard(), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "rarities")
async def rarities(callback: CallbackQuery):
    await callback.message.edit_text(rarity_text(), reply_markup=case_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "open_case")
async def open_case(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    now = time.time()
    remaining = CASE_COOLDOWN - (now - (user["last_case_opened"] or 0))
    if remaining > 0:
        await callback.answer(f"⏳ Кейс на КД: {fmt_time(remaining)}", show_alert=True)
        return
    if user["balance"] < CASE_PRICE:
        await callback.answer(f"Недостаточно денег. Нужно {money(CASE_PRICE)}.", show_alert=True)
        return
    car = choose_car()
    with db() as conn:
        conn.execute("UPDATE users SET balance=balance-?, cases_opened=cases_opened+1, last_case_opened=?, xp=xp+100 WHERE user_id=?", (CASE_PRICE, now, user_id))
        conn.execute("""
            INSERT INTO garage(user_id, car_id, amount) VALUES (?, ?, 1)
            ON CONFLICT(user_id, car_id) DO UPDATE SET amount=amount+1
        """, (user_id, car["id"]))
        row = conn.execute("SELECT amount FROM garage WHERE user_id=? AND car_id=?", (user_id, car["id"])).fetchone()
    r = RARITIES[car["rarity"]]
    duplicate = f"\n📦 Теперь этой машины: <b>{row['amount']} шт.</b>" if row and row["amount"] > 1 else "\n✨ Новая машина в коллекции!"
    result_text = (
        "🎉 <b>КЕЙС ОТКРЫТ!</b>\n\n"
        f"{r['emoji']} <b>{escape(car['rarity'])}</b>\n🚘 <b>{escape(car['name'])}</b>\n"
        f"📅 {car['year']} год\n⚡ {car['power']} л.с.\n💎 Цена: <b>{money(car['price'])}</b>\n"
        f"🎯 Шанс редкости: <b>{r['chance']}%</b>{duplicate}\n\n🏠 Машина добавлена в гараж."
    )
    if car.get("image_file_id"):
        await callback.message.answer_photo(car["image_file_id"], caption=result_text, parse_mode="HTML")
    else:
        await callback.message.answer(result_text, parse_mode="HTML")
    await callback.answer("🚘 Машина получена!")

# =========================================================
# CONTAINERS / AUCTION
# =========================================================

@dp.message(lambda m: m.text == "📦 Контейнеры")
async def containers_menu(message: Message):
    await message.answer(
        "📦 <b>КОНТЕЙНЕРЫ</b>\n\nПокупай контейнеры за игровую валюту и открывай редкие машины.",
        reply_markup=containers_keyboard(message.from_user.id), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "containers:list")
async def containers_list(callback: CallbackQuery):
    await callback.message.edit_text("📦 <b>КОНТЕЙНЕРЫ</b>\n\nВыбери контейнер:", reply_markup=containers_keyboard(callback.from_user.id), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "containers:exclusive")
async def containers_exclusive(callback: CallbackQuery):
    auction = get_auction()
    await callback.message.edit_text(auction_text(auction), reply_markup=auction_keyboard(auction), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "auction:show")
async def auction_show(callback: CallbackQuery):
    auction = get_auction()
    await callback.message.edit_text(auction_text(auction), reply_markup=auction_keyboard(auction), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "auction:bid")
async def auction_bid(callback: CallbackQuery):
    user_id = callback.from_user.id
    now = time.time()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        auction = conn.execute("SELECT * FROM auction WHERE id=1").fetchone()
        if not auction or not auction["active"]:
            conn.rollback(); await callback.answer("Лот завершён.", show_alert=True); return
        if auction["bidder_id"] and auction["ends_at"] <= now:
            conn.rollback(); await callback.answer("Время вышло — дождись завершения аукциона.", show_alert=True); return
        current = auction["current_bid"]
        next_bid = AUCTION_MIN_BID if current == 0 else current + AUCTION_BID_STEP
        user = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or user["balance"] < next_bid:
            conn.rollback(); await callback.answer(f"Нужно {money(next_bid)}.", show_alert=True); return
        # Return the previous leader's reservation.
        if auction["bidder_id"] and auction["bidder_id"] != user_id:
            conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (current, auction["bidder_id"]))
            charge = next_bid
        elif auction["bidder_id"] == user_id:
            charge = next_bid - current
        else:
            charge = next_bid
        conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (charge, user_id))
        conn.execute("UPDATE auction SET current_bid=?, bidder_id=?, ends_at=?, active=1 WHERE id=1", (next_bid, user_id, now + AUCTION_BID_TIME))
        conn.commit()
    auction = get_auction()
    await callback.message.edit_text(auction_text(auction), reply_markup=auction_keyboard(auction), parse_mode="HTML")
    await callback.answer("💰 Ставка принята! Предыдущий лидер получил возврат.")


@dp.callback_query(lambda c: c.data.startswith("container:info:"))
async def container_info(callback: CallbackQuery):
    cid = callback.data.split(":", 2)[2]
    c = CONTAINERS.get(cid)
    if not c:
        await callback.answer("Контейнер не найден.", show_alert=True); return
    await callback.message.edit_text(
        f"{c['emoji']} <b>{escape(c['name'])}</b>\n\n"
        f"💰 Цена: <b>{money(c['price'])}</b>\n📦 У тебя: <b>{get_container_amount(callback.from_user.id, cid)}</b>\n\n"
        f"🎯 Возможные редкости: {', '.join(c['rarities'])}",
        reply_markup=container_info_keyboard(cid, callback.from_user.id), parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("container:buy:"))
async def container_buy(callback: CallbackQuery):
    cid = callback.data.split(":", 2)[2]
    c = CONTAINERS.get(cid)
    if not c:
        await callback.answer("Контейнер не найден.", show_alert=True); return
    with db() as conn:
        user = conn.execute("SELECT balance FROM users WHERE user_id=?", (callback.from_user.id,)).fetchone()
        if not user or user["balance"] < c["price"]:
            await callback.answer(f"Недостаточно денег. Нужно {money(c['price'])}.", show_alert=True); return
        conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (c["price"], callback.from_user.id))
        conn.execute("""INSERT INTO containers(user_id, container_id, amount) VALUES (?, ?, 1)
                       ON CONFLICT(user_id, container_id) DO UPDATE SET amount=amount+1""", (callback.from_user.id, cid))
    await callback.answer("📦 Контейнер куплен!")
    await callback.message.edit_text(
        f"{c['emoji']} <b>{escape(c['name'])}</b>\n\n💰 Цена: <b>{money(c['price'])}</b>\n📦 У тебя: <b>{get_container_amount(callback.from_user.id, cid)}</b>",
        reply_markup=container_info_keyboard(cid, callback.from_user.id), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("container:open:"))
async def container_open(callback: CallbackQuery):
    cid = callback.data.split(":", 2)[2]
    if cid not in CONTAINERS or not remove_container(callback.from_user.id, cid):
        await callback.answer("У тебя нет такого контейнера.", show_alert=True); return
    car = choose_container_car(cid)
    add_car(callback.from_user.id, car["id"])
    add_xp(callback.from_user.id, 150)
    r = RARITIES[car["rarity"]]
    result_text = (
        "🎁 <b>КОНТЕЙНЕР ОТКРЫТ!</b>\n\n"
        f"{r['emoji']} <b>{escape(car['rarity'])}</b>\n🚘 <b>{escape(car['name'])}</b>\n"
        f"📅 {car['year']}  •  ⚡ {car['power']} л.с.\n💎 Цена: <b>{money(car['price'])}</b>\n\n"
        "🏠 Машина добавлена в гараж."
    )
    if car.get("image_file_id"):
        await callback.message.delete()
        await callback.message.answer_photo(car["image_file_id"], caption=result_text, parse_mode="HTML", reply_markup=containers_keyboard(callback.from_user.id))
    else:
        await callback.message.edit_text(result_text, reply_markup=containers_keyboard(callback.from_user.id), parse_mode="HTML")
    await callback.answer("🚘 Машина получена!")

# =========================================================
# GARAGE
# =========================================================

@dp.message(lambda m: m.text == "🏠 Гараж")
async def garage(message: Message):
    await message.answer("🏠 <b>ТВОЙ ГАРАЖ</b>\n\nВыбери раздел:", reply_markup=garage_keyboard(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("garage:"))
async def garage_filter(callback: CallbackQuery):
    rarity = callback.data.split(":", 1)[1]
    await show_garage_page(callback.message, callback.from_user.id, rarity, 0, edit=True)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("gpage:"))
async def garage_page(callback: CallbackQuery):
    _, rarity, page = callback.data.split(":")
    await show_garage_page(callback.message, callback.from_user.id, rarity, int(page), edit=True)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("car:"))
async def car_info(callback: CallbackQuery):
    car_id = int(callback.data.split(":", 1)[1])
    car = CARS_BY_ID.get(car_id)
    if not car:
        await callback.answer("Машина не найдена.", show_alert=True); return
    with db() as conn:
        row = conn.execute("SELECT amount FROM garage WHERE user_id=? AND car_id=?", (callback.from_user.id, car_id)).fetchone()
    if not row or row["amount"] <= 0:
        await callback.answer("Этой машины нет в гараже.", show_alert=True); return
    detail_text = car_caption(car, row["amount"])
    # Оставляем текстовое сообщение с кнопками редактируемым,
    # а фотографию отправляем отдельным сообщением. Так кнопки
    # «Продать» и «В гараж» продолжают работать после просмотра фото.
    await callback.message.edit_text(detail_text, reply_markup=car_keyboard(car_id), parse_mode="HTML")
    if car.get("image_file_id"):
        await callback.message.answer_photo(car["image_file_id"], caption=f"🚘 <b>{escape(car['name'])}</b>", parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("sell:"))
async def sell_one(callback: CallbackQuery):
    _, car_id, amount = callback.data.split(":")
    payout = sell_car(callback.from_user.id, int(car_id), int(amount))
    if not payout:
        await callback.answer("Не удалось продать машину.", show_alert=True); return
    await callback.answer(f"💵 Получено {money(payout)}")
    await show_garage_page(callback.message, callback.from_user.id, "all", 0, edit=True)


@dp.callback_query(lambda c: c.data.startswith("sellall:"))
async def sell_all(callback: CallbackQuery):
    car_id = int(callback.data.split(":", 1)[1])
    with db() as conn:
        row = conn.execute("SELECT amount FROM garage WHERE user_id=? AND car_id=?", (callback.from_user.id, car_id)).fetchone()
    payout = sell_car(callback.from_user.id, car_id, row["amount"] if row else 0)
    if not payout:
        await callback.answer("Машины нет.", show_alert=True); return
    await callback.answer(f"💵 Продано на {money(payout)}")
    await show_garage_page(callback.message, callback.from_user.id, "all", 0, edit=True)


@dp.callback_query(lambda c: c.data == "garage_filters")
async def garage_filters(callback: CallbackQuery):
    await callback.message.edit_text("🔎 <b>ФИЛЬТР ГАРАЖА</b>\n\nВыбери редкость:", reply_markup=garage_keyboard(), parse_mode="HTML")
    await callback.answer()

# =========================================================
# DAILY / QUESTS / SEASON / PROMO / REFERRALS / LEADERBOARD
# =========================================================

@dp.message(lambda m: m.text == "🎁 Бонус дня")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    now = time.time()
    with db() as conn:
        user = conn.execute("SELECT daily_last, daily_streak FROM users WHERE user_id=?", (user_id,)).fetchone()
        last = user["daily_last"] or 0
        if now - last < 86400:
            await message.answer(f"⏳ Бонус уже получен. Возвращайся через <b>{fmt_time(86400-(now-last))}</b>.", parse_mode="HTML")
            return
        streak = user["daily_streak"] + 1 if now-last <= 172800 else 1
        reward = min(2_000_000, 500_000 + (streak-1)*100_000)
        conn.execute("UPDATE users SET daily_last=?, daily_streak=?, balance=balance+?, xp=xp+50 WHERE user_id=?", (now, streak, reward, user_id))
    await message.answer(f"🎁 <b>БОНУС ПОЛУЧЕН!</b>\n\n💰 Награда: <b>{money(reward)}</b>\n🔥 Серия: <b>{streak}</b> дней\n⭐ +50 XP", parse_mode="HTML")


@dp.message(lambda m: m.text == "📝 Квесты")
async def quests(message: Message):
    user = get_user(message.from_user.id)
    rare_owned = any(car["rarity"] in ("Rare", "Epic", "Legendary", "Exclusive", "Secret") for car, _ in get_garage(message.from_user.id))
    lines = ["📝 <b>КВЕСТЫ</b>", ""]
    lines.append(f"1️⃣ Открой 3 кейса — <b>{min(user['cases_opened'],3)}/3</b> • 🎁 500 000₽")
    lines.append(f"2️⃣ Получи Rare+ — <b>{'1/1' if rare_owned else '0/1'}</b> • 🎁 1 000 000₽")
    lines.append(f"3️⃣ Пригласи друга — <b>{min(user['referrals'],1)}/1</b> • 🎁 750 000₽")
    kb = InlineKeyboardBuilder()
    if user["cases_opened"] >= 3 and not user["quest_cases_claimed"]:
        kb.button(text="🎁 Забрать квест 1", callback_data="quest:1")
    if rare_owned and not user["quest_rare_claimed"]:
        kb.button(text="🎁 Забрать квест 2", callback_data="quest:2")
    if user["referrals"] >= 1 and not user["quest_ref_claimed"]:
        kb.button(text="🎁 Забрать квест 3", callback_data="quest:3")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(1)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("quest:"))
async def quest_claim(callback: CallbackQuery):
    q = int(callback.data.split(":")[1])
    uid = callback.from_user.id
    with db() as conn:
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if q == 1 and u["cases_opened"] >= 3 and not u["quest_cases_claimed"]:
            conn.execute("UPDATE users SET balance=balance+500000, quest_cases_claimed=1 WHERE user_id=?", (uid,)); reward=500000
        elif q == 2 and not u["quest_rare_claimed"] and any(c["rarity"] in RARITY_ORDER[2:] for c,_ in get_garage(uid)):
            conn.execute("UPDATE users SET balance=balance+1000000, quest_rare_claimed=1 WHERE user_id=?", (uid,)); reward=1000000
        elif q == 3 and u["referrals"] >= 1 and not u["quest_ref_claimed"]:
            conn.execute("UPDATE users SET balance=balance+750000, quest_ref_claimed=1 WHERE user_id=?", (uid,)); reward=750000
        else:
            await callback.answer("Квест ещё не выполнен или награда уже забрана.", show_alert=True); return
    await callback.answer(f"🎁 Получено {money(reward)}")
    await callback.message.edit_text("✅ <b>Награда получена!</b>\n\nОткрой «📝 Квесты», чтобы проверить остальные.", parse_mode="HTML")


@dp.message(lambda m: m.text == "🏆 Сезон")
async def season(message: Message):
    user = get_user(message.from_user.id)
    level = user["xp"] // 1000 + 1
    current = user["xp"] % 1000
    await message.answer(
        "🏆 <b>СЕЗОН</b>\n\n"
        f"⭐ Уровень: <b>{level}</b>\n✨ Опыт: <b>{current}/1000</b>\n\n"
        "🎁 Кейc: +100 XP\n📦 Контейнер: +150 XP\n🔴 Победа на аукционе: +300 XP\n🎁 Бонус дня: +50 XP",
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🎁 Промокод")
async def promo_help(message: Message):
    await message.answer("🎁 <b>ПРОМОКОД</b>\n\nВведи команду:\n<code>/promo КОД</code>\n\nПример: <code>/promo ZONA100</code>", parse_mode="HTML")


@dp.message(lambda m: (m.text or "").lower().startswith("/promo "))
async def promo_use(message: Message):
    code = message.text.split(maxsplit=1)[1].strip().upper()
    uid = message.from_user.id
    with db() as conn:
        promo = conn.execute("SELECT * FROM promo_codes WHERE code=? AND active=1", (code,)).fetchone()
        if not promo:
            await message.answer("❌ Промокод не найден или отключён."); return
        if promo["max_uses"] > 0 and promo["uses"] >= promo["max_uses"]:
            await message.answer("❌ Лимит активаций промокода исчерпан."); return
        used = conn.execute("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", (uid, code)).fetchone()
        if used:
            await message.answer("⚠️ Ты уже активировал этот промокод."); return
        conn.execute("INSERT INTO promo_used(user_id, code, used_at) VALUES (?, ?, ?)", (uid, code, time.time()))
        conn.execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (code,))
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (promo["reward"], uid))
    await message.answer(f"🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n\n💰 Получено: <b>{money(promo['reward'])}</b>", parse_mode="HTML")


@dp.message(lambda m: m.text == "👥 Реферальная ссылка")
async def referral(message: Message):
    me = await message.bot.get_me()
    user = get_user(message.from_user.id)
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(
        "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"🔗 Твоя ссылка:\n<code>{escape(link)}</code>\n\n"
        f"👤 Приглашено: <b>{user['referrals']}</b>\n💰 Заработано: <b>{money(user['referral_earned'])}</b>\n\n"
        "🎁 За нового игрока: <b>250 000₽</b>", parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🏆 Лидеры")
async def leaders(message: Message):
    with db() as conn:
        by_money = conn.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 5").fetchall()
        by_xp = conn.execute("SELECT user_id, username, xp FROM users ORDER BY xp DESC LIMIT 5").fetchall()
    def name(row): return "@"+row["username"] if row["username"] else f"ID {row['user_id']}"
    text = "🏆 <b>ТОП ИГРОКОВ</b>\n\n💰 <b>По балансу</b>\n"
    for i,r in enumerate(by_money,1): text += f"{i}. {escape(name(r))} — <b>{money(r['balance'])}</b>\n"
    text += "\n⭐ <b>По XP</b>\n"
    for i,r in enumerate(by_xp,1): text += f"{i}. {escape(name(r))} — <b>{r['xp']} XP</b>\n"
    await message.answer(text, parse_mode="HTML")

# =========================================================
# NAVIGATION / ADMIN
# =========================================================

@dp.callback_query(lambda c: c.data == "back_menu")
async def back_menu(callback: CallbackQuery):
    await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nИспользуй кнопки меню ниже.", parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


def is_admin(user_id):
    return user_id == ADMIN_ID


@dp.message(lambda m: m.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа."); return
    await message.answer("👑 <b>АДМИН-ПАНЕЛЬ СОЗДАТЕЛЯ</b>\n\nЗдесь ты можешь выдавать машины игрокам и добавлять новые машины с фотографией.\n\nВыбирай действие кнопками ниже.", reply_markup=admin_keyboard(), parse_mode="HTML")


@dp.message(lambda m: m.text == "/myid")
async def my_id(message: Message):
    await message.answer(f"🆔 Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("admin:"))
async def admin_actions(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    action = callback.data.split(":",1)[1]
    if action == "stats":
        with db() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            cars = conn.execute("SELECT COALESCE(SUM(amount),0) FROM garage").fetchone()[0]
            balance = conn.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
            promos = conn.execute("SELECT COUNT(*) FROM promo_codes WHERE active=1").fetchone()[0]
            custom = conn.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
        text = (f"📊 <b>СТАТИСТИКА</b>\n\n👥 Игроков: <b>{users}</b>\n"
                f"🚘 Машин у игроков: <b>{cars}</b>\n💰 Денег: <b>{money(balance)}</b>\n"
                f"🎁 Активных промокодов: <b>{promos}</b>\n🚗 Всего машин: <b>{len(CARS)}</b>\n➕ Добавлено создателем: <b>{custom}</b>")
        await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    elif action == "auction":
        await callback.message.edit_text(auction_text(get_auction()), reply_markup=admin_keyboard(), parse_mode="HTML")
    elif action == "new_auction":
        start_new_auction()
        await callback.message.edit_text("✅ <b>Новый аукцион создан!</b>\n\n"+auction_text(get_auction()), reply_markup=admin_keyboard(), parse_mode="HTML")
    elif action == "give_car":
        await state.clear()
        await state.set_state(GiveCarState.user_id)
        await callback.message.answer("🚘 <b>ВЫДАЧА МАШИНЫ</b>\n\nВведи Telegram ID игрока:", parse_mode="HTML")
    elif action == "add_car":
        await state.clear()
        await state.set_state(AddCarState.name)
        await callback.message.answer("➕ <b>ДОБАВЛЕНИЕ МАШИНЫ</b>\n\n1️⃣ Введи название машины:", parse_mode="HTML")
    elif action == "custom_cars":
        with db() as conn:
            rows = conn.execute("SELECT id,name,year,power,price,rarity FROM cars ORDER BY id DESC LIMIT 30").fetchall()
        if not rows:
            text = "📋 <b>ДОБАВЛЕННЫЕ МАШИНЫ</b>\n\nПока нет машин, добавленных через админку."
        else:
            text = "📋 <b>ДОБАВЛЕННЫЕ МАШИНЫ</b>\n\n" + "\n".join(
                f"<code>{r['id']}</code> • {RARITIES[r['rarity']]['emoji']} <b>{escape(r['name'])}</b> • {r['year']} • {r['power']} л.с. • {money(r['price'])}"
                for r in rows
            )
        await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.message(AddCarState.name)
async def add_car_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("❌ Название должно быть от 2 до 80 символов. Попробуй ещё раз."); return
    await state.update_data(name=name)
    await state.set_state(AddCarState.year)
    await message.answer("2️⃣ Введи год выпуска (например: 2024):")


@dp.message(AddCarState.year)
async def add_car_year(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: year=int((message.text or "").strip())
    except ValueError: await message.answer("❌ Введи год числом."); return
    if year < 1886 or year > 2100: await message.answer("❌ Некорректный год."); return
    await state.update_data(year=year); await state.set_state(AddCarState.power)
    await message.answer("3️⃣ Введи мощность в л.с. (например: 585):")


@dp.message(AddCarState.power)
async def add_car_power(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: power=int((message.text or "").strip())
    except ValueError: await message.answer("❌ Введи мощность числом."); return
    if power < 1 or power > 10000: await message.answer("❌ Некорректная мощность."); return
    await state.update_data(power=power); await state.set_state(AddCarState.price)
    await message.answer("4️⃣ Введи цену машины в рублях (например: 25000000):")


@dp.message(AddCarState.price)
async def add_car_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: price=int((message.text or "").replace(" ", "").replace("₽", ""))
    except ValueError: await message.answer("❌ Введи цену целым числом."); return
    if price < 1: await message.answer("❌ Цена должна быть больше 0."); return
    await state.update_data(price=price); await state.set_state(AddCarState.rarity)
    text = "5️⃣ Выбери редкость, отправив одно слово:\n\n" + "\n".join(f"{r['emoji']} <b>{rarity}</b>" for rarity,r in RARITIES.items())
    await message.answer(text, parse_mode="HTML")


@dp.message(AddCarState.rarity)
async def add_car_rarity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    value=(message.text or "").strip()
    aliases={"обычная":"Common","common":"Common","uncommon":"Uncommon","rare":"Rare","эпик":"Epic","epic":"Epic","легендарная":"Legendary","legendary":"Legendary","эксклюзив":"Exclusive","exclusive":"Exclusive","секрет":"Secret","secret":"Secret"}
    rarity=aliases.get(value.casefold())
    if not rarity:
        await message.answer("❌ Неизвестная редкость. Напиши Common, Uncommon, Rare, Epic, Legendary, Exclusive или Secret."); return
    await state.update_data(rarity=rarity); await state.set_state(AddCarState.photo)
    await message.answer("6️⃣ Теперь <b>отправь фотографию машины</b> одним сообщением.\n\nИменно эта картинка будет показываться при выпадении и в коллекции.", parse_mode="HTML")


@dp.message(AddCarState.photo)
async def add_car_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.photo:
        await message.answer("❌ Нужна именно фотография. Отправь картинку машины как фото."); return
    data=await state.get_data()
    image_file_id=message.photo[-1].file_id
    car=save_custom_car(data["name"],data["year"],data["power"],data["price"],data["rarity"],image_file_id,message.from_user.id)
    await state.clear()
    r=RARITIES[car["rarity"]]
    caption=(f"✅ <b>МАШИНА ДОБАВЛЕНА!</b>\n\n{car_caption(car,0,False)}\n\n"
             f"🆔 ID машины: <code>{car['id']}</code>\n"
             "🎲 Она уже участвует в выпадении кейсов/контейнеров своей редкости.\n"
             "🏠 Также она будет отображаться в коллекции игроков.")
    await message.answer_photo(image_file_id,caption=caption,parse_mode="HTML",reply_markup=admin_keyboard())


@dp.message(GiveCarState.user_id)
async def give_car_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid=int((message.text or "").strip())
    except ValueError: await message.answer("❌ Telegram ID должен быть числом."); return
    if uid <= 0: await message.answer("❌ Некорректный ID."); return
    ensure_user(uid)
    await state.update_data(user_id=uid); await state.set_state(GiveCarState.car)
    await message.answer("2️⃣ Введи <b>ID машины</b> или её точное/частичное название.\n\nНапример: <code>1001</code> или <code>BMW M5</code>.", parse_mode="HTML")


@dp.message(GiveCarState.car)
async def give_car_car(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    car=find_car_admin((message.text or "").strip())
    if not car:
        await message.answer("❌ Машина не найдена. Введи ID или название ещё раз."); return
    data=await state.get_data(); uid=int(data["user_id"])
    add_car(uid,car["id"],1)
    await state.clear()
    r=RARITIES[car["rarity"]]
    text=(f"✅ Машина выдана игроку <code>{uid}</code>.\n\n"
          f"{r['emoji']} <b>{escape(car['name'])}</b>\n"
          f"📅 {car['year']} • ⚡ {car['power']} л.с. • 💎 {money(car['price'])}")
    if car.get("image_file_id"):
        await message.answer_photo(car["image_file_id"],caption=text,parse_mode="HTML",reply_markup=admin_keyboard())
    else:
        await message.answer(text,parse_mode="HTML",reply_markup=admin_keyboard())


@dp.message(lambda m: (m.text or "").startswith("/give "))
async def admin_give(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        _, uid, amount = message.text.split()
        add_balance(int(uid), int(amount))
        await message.answer(f"✅ Игроку <code>{uid}</code> выдано <b>{money(int(amount))}</b>.", parse_mode="HTML")
    except Exception:
        await message.answer("Формат: /give ID СУММА")


@dp.message(lambda m: (m.text or "").startswith("/addpromo "))
async def admin_addpromo(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        _, code, reward, limit = message.text.split()
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO promo_codes(code,reward,max_uses,uses,active) VALUES(?,?,?,0,1)", (code.upper(), int(reward), int(limit)))
        await message.answer(f"✅ Промокод <code>{escape(code.upper())}</code> создан: <b>{money(int(reward))}</b>, лимит {limit}.", parse_mode="HTML")
    except Exception:
        await message.answer("Формат: /addpromo КОД НАГРАДА ЛИМИТ\nЛимит 0 = безлимитный.")


@dp.message(lambda m: (m.text or "").startswith("/addcontainer "))
async def admin_addcontainer(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        _, uid, cid, amount = message.text.split()
        if cid not in CONTAINERS: raise ValueError
        add_container(int(uid), cid, int(amount))
        await message.answer(f"✅ Выдано: {CONTAINERS[cid]['name']} ×{amount}.")
    except Exception:
        await message.answer("Формат: /addcontainer ID standard|premium|exclusive КОЛ-ВО")

# =========================================================
# RENDER HEALTHCHECK / START
# =========================================================

def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Zona CarCase V2 is running!")
        def log_message(self, format, *args):
            pass
    server = HTTPServer(("0.0.0.0", port), Handler)
    logging.info("WEB SERVER: listening on 0.0.0.0:%s", port)
    server.serve_forever()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    if not TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Установи переменную окружения BOT_TOKEN.")
    init_db()
    load_custom_cars()
    logging.info("Zona CarCase V3 | cars=%s | db=%s", len(CARS), os.path.abspath(DB_FILE))
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    threading.Thread(target=run_web_server, daemon=True).start()
    if not get_auction():
        start_new_auction()
    asyncio.create_task(auction_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
