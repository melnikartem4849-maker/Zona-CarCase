import asyncio
import logging
import os
import random
import sqlite3
import time
import threading
import json
import urllib.parse
import urllib.request
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


dp = Dispatcher()


# =========================================================
# НАСТРОЙКИ
# =========================================================
# ВАЖНО: не вставляй токен прямо в код.
# Перед запуском в CMD выполни:
# set BOT_TOKEN="ТВОЙ_ТОКЕН"
TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "zonacarcase.db"
CAR_IMAGES_DIR = "car_images"
COLLECTION_IMAGE = os.path.join(CAR_IMAGES_DIR, "collection.jpg")
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
# БАЗА ДАННЫХ
# =========================================================
def db():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
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
                username TEXT NOT NULL DEFAULT '',
                first_name TEXT NOT NULL DEFAULT '',
                last_daily REAL NOT NULL DEFAULT 0,
                referrals INTEGER NOT NULL DEFAULT 0,
                referral_earnings INTEGER NOT NULL DEFAULT 0
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

        # Если база была создана старой версией бота, добавляем колонку КД.
        auction_columns = [row[1] for row in conn.execute("PRAGMA table_info(auction)").fetchall()]
        if "created_at" not in auction_columns:
            conn.execute("ALTER TABLE auction ADD COLUMN created_at REAL NOT NULL DEFAULT 0")

        columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "last_case_opened" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_case_opened REAL NOT NULL DEFAULT 0")

        columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        for column, definition in [
            ("username", "TEXT NOT NULL DEFAULT ''"),
            ("first_name", "TEXT NOT NULL DEFAULT ''"),
            ("last_daily", "REAL NOT NULL DEFAULT 0"),
            ("referrals", "INTEGER NOT NULL DEFAULT 0"),
            ("referral_earnings", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if column not in columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")


def ensure_user(user_id):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id) VALUES (?)",
            (user_id,)
        )


def get_user(user_id):
    ensure_user(user_id)
    with db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def add_balance(user_id, amount):
    with db() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )


def add_xp(user_id, amount):
    with db() as conn:
        conn.execute(
            "UPDATE users SET xp = xp + ? WHERE user_id = ?",
            (amount, user_id)
        )


def add_car(user_id, car_id):
    with db() as conn:
        conn.execute("""
            INSERT INTO garage(user_id, car_id, amount)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, car_id)
            DO UPDATE SET amount = amount + 1
        """, (user_id, car_id))


def get_garage(user_id, rarity=None):
    query = """
        SELECT g.car_id, g.amount
        FROM garage g
        WHERE g.user_id = ? AND g.amount > 0
    """
    params = [user_id]
    if rarity:
        query += " AND g.car_id IN (SELECT id FROM temp_cars WHERE rarity = ?)"
        # Не используем temp_cars — фильтрация ниже проще и надёжнее.
        query = """
            SELECT g.car_id, g.amount
            FROM garage g
            WHERE g.user_id = ? AND g.amount > 0
        """
    with db() as conn:
        rows = conn.execute(query, (user_id,)).fetchall()

    result = []
    for row in rows:
        car = CARS_BY_ID.get(row["car_id"])
        if car and (rarity is None or car["rarity"] == rarity):
            result.append((car, row["amount"]))
    result.sort(key=lambda x: (RARITY_ORDER.index(x[0]["rarity"]), x[0]["name"]))
    return result


def get_container_amount(user_id, container_id):
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM containers WHERE user_id=? AND container_id=?",
            (user_id, container_id)
        ).fetchone()
    return row["amount"] if row else 0


def add_container(user_id, container_id, amount=1):
    with db() as conn:
        conn.execute("""
            INSERT INTO containers(user_id, container_id, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, container_id)
            DO UPDATE SET amount = amount + excluded.amount
        """, (user_id, container_id, amount))


def remove_container(user_id, container_id, amount=1):
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM containers WHERE user_id=? AND container_id=?",
            (user_id, container_id)
        ).fetchone()
        if not row or row["amount"] < amount:
            return False
        conn.execute(
            "UPDATE containers SET amount=amount-? WHERE user_id=? AND container_id=?",
            (amount, user_id, container_id)
        )
        conn.execute("DELETE FROM containers WHERE amount <= 0")
    return True


def choose_container_car(container_id):
    container = CONTAINERS[container_id]
    rarity = random.choice(container["rarities"])
    return random.choice(CARS_BY_RARITY[rarity])


def exclusive_cars():
    return CARS_BY_RARITY["Exclusive"] + CARS_BY_RARITY["Secret"]


def sell_car(user_id, car_id, amount=1):
    car = CARS_BY_ID.get(car_id)
    if not car or amount < 1:
        return 0

    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (user_id, car_id)
        ).fetchone()
        if not row or row["amount"] < amount:
            return 0

        payout = int(car["price"] * RARITIES[car["rarity"]]["sell"]) * amount
        conn.execute(
            "UPDATE garage SET amount = amount - ? WHERE user_id=? AND car_id=?",
            (amount, user_id, car_id)
        )
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (payout, user_id)
        )
        conn.execute(
            "DELETE FROM garage WHERE amount <= 0"
        )
        return payout


# =========================================================
# АУКЦИОН ЭКСКЛЮЗИВНЫХ МАШИН
# =========================================================
def get_auction():
    with db() as conn:
        return conn.execute("SELECT * FROM auction WHERE id=1").fetchone()


def start_new_auction():
    cars = CARS_BY_RARITY["Exclusive"]
    if not cars:
        return None
    car = random.choice(cars)
    with db() as conn:
        now = time.time()
        conn.execute("""
            INSERT INTO auction(id, car_id, current_bid, bidder_id, ends_at, created_at, active)
            VALUES (1, ?, 0, NULL, 0, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                car_id=excluded.car_id,
                current_bid=0,
                bidder_id=NULL,
                ends_at=0,
                created_at=?,
                active=1
        """, (car["id"], now, now))
    return car


def auction_text(auction):
    if not auction:
        return "🔴 <b>ЭКСКЛЮЗИВНЫЙ АУКЦИОН</b>\n\nЛот скоро появится."
    car = CARS_BY_ID.get(auction["car_id"])
    if not car:
        return "🔴 <b>ЭКСКЛЮЗИВНЫЙ АУКЦИОН</b>\n\nЛот не найден."
    bid = auction["current_bid"]
    if auction["bidder_id"] and auction["ends_at"] > time.time():
        left = max(0, int(auction["ends_at"] - time.time()))
        timer = f"⏳ До окончания ставки: <b>00:{left:02d}</b>"
    else:
        timer = "⏳ Ставок пока нет — поставь первую ставку."
    bid_text = money(bid) if bid else "нет ставок"
    next_bid = AUCTION_MIN_BID if bid == 0 else bid + AUCTION_BID_STEP
    return (
        "🔴 <b>ЭКСКЛЮЗИВНЫЙ АУКЦИОН</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🚘 <b>{escape(car['name'])}</b>\n"
        f"📅 Год: <b>{car['year']}</b>\n"
        f"⚡ Мощность: <b>{car['power']} л.с.</b>\n"
        f"💎 Стоимость машины: <b>{money(car['price'])}</b>\n\n"
        f"💰 Текущая ставка: <b>{bid_text}</b>\n"
        f"⬆️ Следующая ставка: <b>{money(next_bid)}</b>\n"
        f"{timer}\n\n"
        "🏆 Победитель получает машину в гараж.\n"
        "💸 Деньги за лот списываются только после победы."
    )


def auction_keyboard(auction):
    kb = InlineKeyboardBuilder()
    if auction:
        bid = auction["current_bid"]
        next_bid = AUCTION_MIN_BID if bid == 0 else bid + AUCTION_BID_STEP
        kb.button(text=f"💰 Ставка {money(next_bid)}", callback_data="auction:bid")
    kb.button(text="🔄 Обновить", callback_data="auction:show")
    kb.button(text="⬅️ Контейнеры", callback_data="containers:list")
    kb.adjust(1)
    return kb.as_markup()


async def finish_auction():
    auction = get_auction()
    if not auction or not auction["active"] or not auction["bidder_id"]:
        return False
    if auction["ends_at"] > time.time():
        return False
    car = CARS_BY_ID.get(auction["car_id"])
    if not car:
        return False
    winner_id = auction["bidder_id"]
    bid = auction["current_bid"]
    user = get_user(winner_id)
    if user["balance"] < bid:
        with db() as conn:
            conn.execute("UPDATE auction SET active=0, created_at=? WHERE id=1", (time.time(),))
        return False
    with db() as conn:
        conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (bid, winner_id))
        conn.execute("UPDATE auction SET active=0, created_at=? WHERE id=1", (time.time(),))
    add_car(winner_id, car["id"])
    add_xp(winner_id, 300)
    return winner_id, car, bid


async def auction_loop(bot):
    while True:
        try:
            result = await finish_auction()
            if result:
                winner_id, car, bid = result
                try:
                    path = make_car_image(car)
                    caption = (
                        "🏆 <b>ТЫ ПОБЕДИЛ В АУКЦИОНЕ!</b>\n\n"
                        + car_caption(car, 1) + "\n"
                        f"💰 Ставка: <b>{money(bid)}</b>\n"
                        "🚘 Машина добавлена в гараж!"
                    )
                    if path:
                        await bot.send_photo(winner_id, FSInputFile(path), caption=caption, parse_mode="HTML")
                    else:
                        await bot.send_message(winner_id, caption, parse_mode="HTML")
                except Exception:
                    pass
            auction = get_auction()
            now = time.time()
            if not auction:
                start_new_auction()
            elif not auction["active"]:
                # После победы оставляем аукцион неактивным на час.
                if now - auction["created_at"] >= AUCTION_INTERVAL:
                    start_new_auction()
            elif now - auction["created_at"] >= AUCTION_INTERVAL and not auction["bidder_id"]:
                # Если за час никто не сделал ставку — запускаем новый лот.
                start_new_auction()
        except Exception:
            logging.exception("Ошибка аукциона")
        await asyncio.sleep(1)


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================
def is_admin(user_id):
    return user_id == ADMIN_ID

def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin:stats")
    kb.button(text="🔴 Текущий аукцион", callback_data="admin:auction")
    kb.button(text="🚘 Новый аукцион", callback_data="admin:new_auction")
    kb.adjust(1)
    return kb.as_markup()

@dp.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return
    await message.answer("👑 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:", reply_markup=admin_keyboard(), parse_mode="HTML")

@dp.message(lambda message: message.text == "/myid")
async def my_id(message: Message):
    await message.answer(f"🆔 Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("admin:"))
async def admin_actions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    if action == "stats":
        with db() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            cars_count = conn.execute("SELECT COUNT(*) FROM garage").fetchone()[0]
            balance = conn.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
        await callback.message.edit_text(
            "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
            f"👥 Игроков: <b>{users_count}</b>\n"
            f"🚘 Машин в гаражах: <b>{cars_count}</b>\n"
            f"💰 Общий баланс игроков: <b>{money(balance)}</b>",
            reply_markup=admin_keyboard(), parse_mode="HTML"
        )
    elif action == "auction":
        auction = get_auction()
        text = auction_text(auction) if auction and auction["active"] else "🔴 Щечас нет активного аукциона!\nЖди завоза."
        await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    elif action == "new_auction":
        start_new_auction()
        auction = get_auction()
        await callback.message.edit_text("✅ <b>Новый аукцион создан!</b>\n\n" + auction_text(auction), reply_markup=admin_keyboard(), parse_mode="HTML")
    await callback.answer()


# =========================================================
# КЛАВИАТУРЫ
# =========================================================
def main_keyboard():
    kb = ReplyKeyboardBuilder()
    for text in [
        "🚘 Открыть авто",
        "🏠 Гараж",
        "📖 Коллекция",
        "📦 Контейнеры",
        "👤 Профиль",
        "📝 Квесты",
        "🏆 Сезон",
        "🎁 Промокод",
        "🎁 Ежедневный бонус",
        "👥 Реферальная ссылка",
    ]:
        kb.button(text=text)
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


def case_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 ОТКРЫТЬ КЕЙС", callback_data="open_case")
    kb.button(text="📊 Редкости", callback_data="rarities")
    kb.button(text="⬅️ Назад", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def containers_tabs(active="containers"):
    kb = InlineKeyboardBuilder()
    left = "✅ 📦 Контейнеры" if active == "containers" else "📦 Контейнеры"
    right = "✅ 🔴 Эксклюзивные машины" if active == "exclusive" else "🔴 Эксклюзивные машины"
    kb.button(text=left, callback_data="containers:list")
    kb.button(text=right, callback_data="containers:exclusive")
    kb.adjust(2)
    return kb


def containers_keyboard(user_id):
    kb = containers_tabs("containers")
    for container_id, c in CONTAINERS.items():
        amount = get_container_amount(user_id, container_id)
        kb.button(
            text=f'{c["emoji"]} {c["name"]} • {money(c["price"])} • ×{amount}',
            callback_data=f"container:info:{container_id}"
        )
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def exclusive_keyboard():
    kb = containers_tabs("exclusive")
    kb.button(text="🔴 Открыть текущий аукцион", callback_data="auction:show")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def container_info_keyboard(container_id, user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Купить 1", callback_data=f"container:buy:{container_id}")
    amount = get_container_amount(user_id, container_id)
    if amount > 0:
        kb.button(text="🎁 Открыть 1", callback_data=f"container:open:{container_id}")
    kb.button(text="⬅️ Контейнеры", callback_data="containers:list")
    kb.adjust(1)
    return kb.as_markup()


def garage_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Все машины", callback_data="garage:all")
    for rarity in RARITY_ORDER:
        kb.button(
            text=f'{RARITIES[rarity]["emoji"]} {rarity}',
            callback_data=f"garage:{rarity}"
        )
    kb.button(text="⬅️ Назад", callback_data="back_menu")
    kb.adjust(2)
    return kb.as_markup()


def garage_page_keyboard(items, page, rarity):
    kb = InlineKeyboardBuilder()
    start = page * 8
    page_items = items[start:start + 8]

    for car, amount in page_items:
        kb.button(
            text=f'{RARITIES[car["rarity"]]["emoji"]} {car["name"]} ×{amount}',
            callback_data=f'car:{car["id"]}'
        )
    kb.adjust(1)

    total_pages = max(1, (len(items) + 7) // 8)
    if total_pages > 1:
        if page > 0:
            kb.button(
                text="⬅️",
                callback_data=f"gpage:{rarity or 'all'}:{page-1}"
            )
        kb.button(text=f"{page+1}/{total_pages}", callback_data="noop")
        if page + 1 < total_pages:
            kb.button(
                text="➡️",
                callback_data=f"gpage:{rarity or 'all'}:{page+1}"
            )

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


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================
def money(value):
    return "$" + f"{value:,}".replace(",", " ")


def rarity_text():
    lines = ["⭐ <b>РЕДКОСТИ И ШАНСЫ</b>", ""]
    for rarity in RARITY_ORDER:
        r = RARITIES[rarity]
        lines.append(
            f'{r["emoji"]} <b>{rarity}</b> — {r["chance"]}% '
            f'• {len(CARS_BY_RARITY[rarity])} машин'
        )
    return "\n".join(lines)


def choose_car():
    rarity = random.choices(
        RARITY_ORDER,
        weights=[RARITIES[r]["chance"] for r in RARITY_ORDER],
        k=1
    )[0]
    return random.choice(CARS_BY_RARITY[rarity])


def garage_summary(user_id):
    items = get_garage(user_id)
    unique = len(items)
    total = sum(amount for _, amount in items)
    return unique, total


# =========================================================
# ИЗОБРАЖЕНИЯ МАШИН
# =========================================================
def _safe_image_name(name):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _car_image_candidates(car):
    cid = car["id"]
    safe = _safe_image_name(car["name"])
    base = os.path.join(CAR_IMAGES_DIR)
    candidates = []
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidates.append(os.path.join(base, f"{cid}.{ext}"))
        candidates.append(os.path.join(base, f"{safe}.{ext}"))
    return candidates


def make_car_image(car):
    """Получить настоящее фото конкретной модели из Wikimedia Commons.

    Сначала проверяем локальный кэш. Если фото нет, ищем модель через API
    Wikimedia Commons, скачиваем thumbnail и сохраняем его в car_images/.
    Если интернет временно недоступен, возвращаем локальную карточку-заглушку.
    """
    os.makedirs(CAR_IMAGES_DIR, exist_ok=True)

    for path in _car_image_candidates(car):
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            return path

    safe = _safe_image_name(car["name"])
    out = os.path.join(CAR_IMAGES_DIR, f"{car['id']}.jpg")
    source_file = os.path.join(CAR_IMAGES_DIR, f"{car['id']}.source.txt")

    # Ищем именно страницу файла в Wikimedia Commons.
    queries = [
        f"{car['name']} {car['year']}",
        car["name"],
        car["name"].replace("_", " "),
    ]
    try:
        for search in queries:
            params = {
                "action": "query",
                "generator": "search",
                "gsrsearch": search,
                "gsrnamespace": 6,
                "gsrlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": 1200,
                "format": "json",
                "origin": "*",
            }
            url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "ZonaCarCase/2.0 (Telegram bot)"})
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8"))

            pages = list((data.get("query", {}).get("pages", {}) or {}).values())
            for page in pages:
                info = (page.get("imageinfo") or [{}])[0]
                image_url = info.get("thumburl") or info.get("url")
                mime = (info.get("mime") or "").lower()
                if not image_url or mime not in ("image/jpeg", "image/png", "image/webp"):
                    continue
                try:
                    img_req = urllib.request.Request(
                        image_url,
                        headers={"User-Agent": "ZonaCarCase/2.0 (Telegram bot)"}
                    )
                    with urllib.request.urlopen(img_req, timeout=20) as img_response:
                        raw = img_response.read()
                    if len(raw) < 5000:
                        continue
                    # Приводим PNG/WebP/JPEG к обычному JPEG, который Telegram принимает.
                    from PIL import Image
                    import io
                    image = Image.open(io.BytesIO(raw)).convert("RGB")
                    tmp = out + ".tmp"
                    image.save(tmp, "JPEG", quality=90, optimize=True)
                    os.replace(tmp, out)
                    with open(source_file, "w", encoding="utf-8") as f:
                        f.write(image_url)
                    return out
                except Exception:
                    continue
    except Exception:
        logging.exception("Не удалось скачать фото для %s", car["name"])

    # Надёжная заглушка, если Wikimedia временно недоступна.
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1280, 720), (14, 18, 24))
        d = ImageDraw.Draw(img)
        bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        regular_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        title_font = ImageFont.truetype(bold_path, 52)
        text_font = ImageFont.truetype(regular_path, 30)
        d.rounded_rectangle((45, 45, 1235, 675), radius=30, outline=(100, 110, 125), width=3)
        d.text((80, 90), car["name"], font=title_font, fill=(245, 245, 245))
        d.text((82, 175), f"{car['year']}  •  {car['power']} л.с.", font=text_font, fill=(190, 200, 215))
        d.text((82, 225), f"Стоимость: {money(car['price'])}", font=text_font, fill=(220, 225, 235))
        d.text((82, 600), "Фото временно недоступно — попробуйте открыть машину ещё раз.", font=text_font, fill=(150, 160, 175))
        img.save(out, "JPEG", quality=90)
        return out
    except Exception:
        return None

def make_collection_cover():
    os.makedirs(CAR_IMAGES_DIR, exist_ok=True)
    if os.path.isfile(COLLECTION_IMAGE):
        return COLLECTION_IMAGE
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (11, 16, 23))
    d = ImageDraw.Draw(img)
    for i in range(6):
        x = 70 + i * 205
        d.rounded_rectangle((x, 240-(i%2)*25, x+180, 520), radius=25, fill=(30+i*4, 37+i*4, 48+i*5), outline=(90, 100, 115), width=2)
    title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    d.text((70, 70), "📖 КОЛЛЕКЦИЯ", font=title, fill=(245,245,245))
    d.text((75, 155), "306 автомобилей • собирай редкие модели", font=sub, fill=(185,195,210))
    img.save(COLLECTION_IMAGE, "JPEG", quality=92)
    return COLLECTION_IMAGE


def car_caption(car, amount=1, prefix="🚘"):
    r = RARITIES[car["rarity"]]
    return (
        f"{prefix} <b>{escape(car['name'])}</b>\n\n"
        f"{r['emoji']} Редкость: <b>{escape(car['rarity'])}</b>\n"
        f"📅 Год: <b>{car['year']}</b>\n"
        f"⚡ Мощность: <b>{car['power']} л.с.</b>\n"
        f"💎 Стоимость: <b>{money(car['price'])}</b>\n"
        f"📦 В гараже: <b>{amount} шт.</b>"
    )


def make_season_image():
    os.makedirs(CAR_IMAGES_DIR, exist_ok=True)
    path = os.path.join(CAR_IMAGES_DIR, "season1.jpg")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    with db() as conn:
        rows = conn.execute(
            "SELECT user_id, username, first_name, xp, cases_opened FROM users ORDER BY xp DESC, cases_opened DESC LIMIT 10"
        ).fetchall()

    W, H = 1400, 1100
    img = Image.new("RGB", (W, H), (12, 16, 23))
    d = ImageDraw.Draw(img)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    white=(245,245,245); muted=(175,185,200)

    d.text((70, 45), "🏆 СЕЗОН 1", font=title, fill=white)
    d.text((74, 130), "Лидерборд сезона • топ игроков по XP", font=small, fill=muted)

    # podium
    d.rounded_rectangle((430, 190, 970, 360), radius=30, fill=(37, 42, 52), outline=(105, 115, 130), width=3)
    d.text((700, 235), "🥇 1", font=bold, fill=white, anchor="mm")
    d.text((525, 285), "🥈 2", font=bold, fill=white, anchor="mm")
    d.text((875, 285), "🥉 3", font=bold, fill=white, anchor="mm")

    y=405
    for i,row in enumerate(rows,1):
        name = ("@" + row["username"]) if row["username"] else (row["first_name"] or f"Игрок {row['user_id']}")
        if len(name)>24: name=name[:23]+"…"
        bg=(28,34,43) if i%2 else (23,29,37)
        d.rounded_rectangle((60,y,W-60,y+58), radius=15, fill=bg)
        medal = {1:"🥇",2:"🥈",3:"🥉"}.get(i,f"{i}.")
        d.text((82,y+29), medal, font=small, fill=white, anchor="lm")
        d.text((160,y+29), name, font=bold if i<=3 else small, fill=white, anchor="lm")
        d.text((860,y+29), f"⭐ {row['xp']:,} XP".replace(","," "), font=small, fill=white, anchor="lm")
        d.text((1110,y+29), f"🎁 {row['cases_opened']}", font=small, fill=muted, anchor="lm")
        y += 65
    d.text((70, 1060), "Призы выдаются автоматически в конце сезона.", font=small, fill=muted)
    img.save(path,"JPEG",quality=92)
    return path


async def send_car_result(target, car, title="🎉 <b>МАШИНА ВЫПАЛА!</b>", amount=1, reply_markup=None):
    path = make_car_image(car)
    caption = title + "\n\n" + car_caption(car, amount)
    if path:
        await target.answer_photo(FSInputFile(path), caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await target.answer(caption, reply_markup=reply_markup, parse_mode="HTML")


# =========================================================
# HANDLERS
# =========================================================

def register_user(message: Message):
    ensure_user(message.from_user.id)
    with db() as conn:
        conn.execute(
            "UPDATE users SET username=?, first_name=? WHERE user_id=?",
            (message.from_user.username or "", message.from_user.first_name or "", message.from_user.id)
        )


def today_start():
    now = time.time()
    return now - (now % 86400)


def claim_daily(user_id):
    ensure_user(user_id)
    now = time.time()
    with db() as conn:
        row = conn.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row and row["last_daily"] >= today_start():
            return False
        conn.execute(
            "UPDATE users SET balance=balance+500000, xp=xp+50, last_daily=? WHERE user_id=?",
            (now, user_id)
        )
    return True


@dp.message(CommandStart())
async def start(message: Message):
    register_user(message)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) != message.from_user.id:
        referrer_id = int(parts[1])
        ensure_user(referrer_id)
        with db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, invited_id INTEGER UNIQUE, created_at REAL)")
            try:
                conn.execute("INSERT INTO referrals(referrer_id, invited_id, created_at) VALUES (?, ?, ?)", (referrer_id, message.from_user.id, time.time()))
                conn.execute("UPDATE users SET referrals=referrals+1, referral_earnings=referral_earnings+500000, balance=balance+500000, xp=xp+100 WHERE user_id=?", (referrer_id,))
                conn.execute("UPDATE users SET balance=balance+500000, xp=xp+100 WHERE user_id=?", (message.from_user.id,))
            except sqlite3.IntegrityError:
                pass
    user = get_user(message.from_user.id)
    await message.answer(
        "🚘 <b>Добро пожаловать в Zona CarCase!</b>\n\n"
        "🎁 Открывай кейсы\n"
        "🏠 Собирай машины в гараже\n"
        "⭐ Собирай все 7 редкостей\n"
        "💰 Продавай дубликаты\n\n"
        f"💰 Баланс: <b>{money(user['balance'])}</b>\n"
        f"🚗 В коллекции: <b>{garage_summary(message.from_user.id)[0]}/306</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(message: Message):
    register_user(message)
    user = get_user(message.from_user.id)
    unique, total = garage_summary(message.from_user.id)
    level = user["xp"] // 1000 + 1
    current_xp = user["xp"] % 1000
    progress = int(current_xp / 1000 * 10)
    xp_bar = "🟩" * progress + "⬜" * (10 - progress)

    await message.answer(
        "👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"💰 Баланс\n<b>{money(user['balance'])}</b>\n\n"
        f"⭐ Уровень: <b>{level}</b>\n"
        f"{xp_bar} <b>{current_xp}/1000 XP</b>\n\n"
        "🚘 КОЛЛЕКЦИЯ\n"
        f"🏠 Уникальных машин: <b>{unique}/306</b>\n"
        f"📦 Всего машин: <b>{total}</b>\n\n"
        "🎁 КЕЙСЫ\n"
        f"Открыто кейсов: <b>{user['cases_opened']}</b>\n\n"
        "💎 Собирай редкие машины и повышай уровень!",
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🚘 Открыть авто")
async def open_auto(message: Message):
    await message.answer(
        "🎁 <b>COMMON CASE</b>\n\n"
        f"💰 Цена: <b>{money(CASE_PRICE)}</b>\n⏳ КД: <b>3 часа</b>\n\n"
        "⭐ Шансы:\n"
        "⚪ Common — 60%\n"
        "🟢 Uncommon — 25%\n"
        "🔵 Rare — 10%\n"
        "🟣 Epic — 3%\n"
        "🟡 Legendary — 1.5%\n"
        "🔴 Exclusive — 0.4%\n"
        "⚫ Secret — 0.1%\n\n"
        "Нажми кнопку, чтобы открыть кейс 👇",
        reply_markup=case_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "rarities")
async def rarities(callback: CallbackQuery):
    await callback.message.edit_text(
        rarity_text(),
        reply_markup=case_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "open_case")
async def open_case(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)

    now = time.time()
    last_case = user["last_case_opened"] or 0
    remaining = CASE_COOLDOWN - (now - last_case)

    if remaining > 0:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        await callback.answer(
            f"⏳ Кейс пока на КД. Осталось: {hours:02d}:{minutes:02d}:{seconds:02d}",
            show_alert=True
        )
        return

    if user["balance"] < CASE_PRICE:
        await callback.answer(
            f"Недостаточно денег. Нужно {money(CASE_PRICE)}.",
            show_alert=True
        )
        return

    car = choose_car()

    with db() as conn:
        conn.execute(
            "UPDATE users SET balance=balance-?, cases_opened=cases_opened+1, last_case_opened=? WHERE user_id=?",
            (CASE_PRICE, now, user_id)
        )

    add_car(user_id, car["id"])
    add_xp(user_id, 100)

    r = RARITIES[car["rarity"]]
    duplicate_text = ""
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (user_id, car["id"])
        ).fetchone()
        if row and row["amount"] > 1:
            duplicate_text = f"\n📦 Теперь этой машины у тебя: <b>{row['amount']} шт.</b>"

    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (user_id, car["id"])
        ).fetchone()
    amount = row["amount"] if row else 1
    caption_title = (
        "🎉 <b>КЕЙС ОТКРЫТ!</b>\n\n"
        f"🎯 Шанс редкости: <b>{r['chance']}%</b>"
        f"{duplicate_text}"
    )
    path = make_car_image(car)
    caption = caption_title + "\n\n" + car_caption(car, amount)
    if path:
        await callback.message.answer_photo(FSInputFile(path), caption=caption, reply_markup=case_keyboard(), parse_mode="HTML")
    else:
        await callback.message.answer(caption, reply_markup=case_keyboard(), parse_mode="HTML")
    await callback.answer("🚘 Машина добавлена в гараж!")


@dp.message(lambda m: m.text == "📦 Контейнеры")
async def containers_menu(message: Message):
    await message.answer(
        "📦 <b>КОНТЕЙНЕРЫ</b>\n\n"
        "Покупай контейнеры и открывай дополнительные машины.\n"
        "🔴 Во вкладке «Эксклюзивные машины» можно посмотреть весь эксклюзив.",
        reply_markup=containers_keyboard(message.from_user.id),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "containers:list")
async def containers_list_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>КОНТЕЙНЕРЫ</b>\n\n"
        "Выбери контейнер. Внутри выпадет 1 машина из указанных редкостей.",
        reply_markup=containers_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "containers:exclusive")
async def containers_exclusive_callback(callback: CallbackQuery):
    auction = get_auction()
    await callback.message.edit_text(
        auction_text(auction),
        reply_markup=auction_keyboard(auction),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "auction:show")
async def auction_show(callback: CallbackQuery):
    auction = get_auction()
    if not auction or not auction["active"]:
        await callback.answer("🔴 Щечас нет активного аукциона! Жди завоза", show_alert=True)
        return
    await callback.message.edit_text(
        auction_text(auction),
        reply_markup=auction_keyboard(auction),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "auction:bid")
async def auction_bid(callback: CallbackQuery):
    user_id = callback.from_user.id
    auction = get_auction()
    if not auction or not auction["active"]:
        await callback.answer("Лот уже завершён. Жди следующий.", show_alert=True)
        return

    # Если старая ставка уже закончилась — сначала завершаем лот.
    if auction["bidder_id"] and auction["ends_at"] <= time.time():
        result = await finish_auction()
        if result:
            await callback.answer("Аукцион уже завершён. Машина ушла победителю.", show_alert=True)
        else:
            await callback.answer("Аукцион уже завершён.", show_alert=True)
        return

    current = auction["current_bid"]
    next_bid = AUCTION_MIN_BID if current == 0 else current + AUCTION_BID_STEP
    user = get_user(user_id)
    if user["balance"] < next_bid:
        await callback.answer(f"Нужно минимум {money(next_bid)}.", show_alert=True)
        return

    with db() as conn:
        conn.execute(
            "UPDATE auction SET current_bid=?, bidder_id=?, ends_at=?, active=1 WHERE id=1",
            (next_bid, user_id, time.time() + AUCTION_BID_TIME)
        )
    await callback.answer("💰 Ставка принята! Отсчёт 1 минута.")
    auction = get_auction()
    await callback.message.edit_text(
        auction_text(auction),
        reply_markup=auction_keyboard(auction),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("container:info:"))
async def container_info(callback: CallbackQuery):
    container_id = callback.data.split(":", 2)[2]
    c = CONTAINERS.get(container_id)
    if not c:
        await callback.answer("Контейнер не найден.", show_alert=True)
        return
    amount = get_container_amount(callback.from_user.id, container_id)
    rarities = ", ".join(
        f'{RARITIES[r]["emoji"]} {r}' for r in c["rarities"]
    )
    await callback.message.edit_text(
        f'{c["emoji"]} <b>{escape(c["name"])}</b>\n\n'
        f'💰 Цена: <b>{money(c["price"])}</b>\n'
        f'📦 У тебя: <b>{amount} шт.</b>\n'
        f'🎯 Возможные редкости: <b>{rarities}</b>\n\n'
        "Купи контейнер или открой уже имеющийся.",
        reply_markup=container_info_keyboard(container_id, callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("container:buy:"))
async def container_buy(callback: CallbackQuery):
    container_id = callback.data.split(":", 2)[2]
    c = CONTAINERS.get(container_id)
    if not c:
        await callback.answer("Контейнер не найден.", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    if user["balance"] < c["price"]:
        await callback.answer(f'Нужно {money(c["price"])}.', show_alert=True)
        return
    with db() as conn:
        conn.execute(
            "UPDATE users SET balance=balance-? WHERE user_id=?",
            (c["price"], callback.from_user.id)
        )
    add_container(callback.from_user.id, container_id, 1)
    await callback.answer("📦 Контейнер куплен!")
    amount = get_container_amount(callback.from_user.id, container_id)
    await callback.message.edit_text(
        f'{c["emoji"]} <b>{escape(c["name"])}</b>\n\n'
        f'💰 Цена: <b>{money(c["price"])}</b>\n'
        f'📦 У тебя: <b>{amount} шт.</b>\n\n'
        "Контейнер готов к открытию!",
        reply_markup=container_info_keyboard(container_id, callback.from_user.id),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("container:open:"))
async def container_open(callback: CallbackQuery):
    container_id = callback.data.split(":", 2)[2]
    c = CONTAINERS.get(container_id)
    if not c:
        await callback.answer("Контейнер не найден.", show_alert=True)
        return
    if get_container_amount(callback.from_user.id, container_id) <= 0:
        await callback.answer("У тебя нет такого контейнера.", show_alert=True)
        return
    remove_container(callback.from_user.id, container_id, 1)
    car = choose_container_car(container_id)
    add_car(callback.from_user.id, car["id"])
    add_xp(callback.from_user.id, 150)
    r = RARITIES[car["rarity"]]
    path = make_car_image(car)
    caption = "🎉 <b>КОНТЕЙНЕР ОТКРЫТ!</b>\n\n" + car_caption(car) + "\n\n🏠 Машина добавлена в гараж."
    if path:
        await callback.message.answer_photo(FSInputFile(path), caption=caption, reply_markup=containers_keyboard(callback.from_user.id), parse_mode="HTML")
    else:
        await callback.message.answer(caption, reply_markup=containers_keyboard(callback.from_user.id), parse_mode="HTML")
    await callback.answer("🚘 Машина добавлена в гараж!")


@dp.callback_query(lambda c: c.data.startswith("exclusive:car:"))
async def exclusive_car_info(callback: CallbackQuery):
    car_id = int(callback.data.split(":")[-1])
    car = CARS_BY_ID.get(car_id)
    if not car or car["rarity"] not in ("Exclusive", "Secret"):
        await callback.answer("Эксклюзивная машина не найдена.", show_alert=True)
        return
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (callback.from_user.id, car_id)
        ).fetchone()
    amount = row["amount"] if row else 0
    r = RARITIES[car["rarity"]]
    await callback.message.edit_text(
        f'{r["emoji"]} <b>{escape(car["name"])}</b>\n\n'
        f'⭐ Редкость: <b>{escape(car["rarity"])}</b>\n'
        f'📅 Год: <b>{car["year"]}</b>\n'
        f'⚡ Мощность: <b>{car["power"]} л.с.</b>\n'
        f'💎 Стоимость: <b>{money(car["price"])}</b>\n'
        f'📦 В гараже: <b>{amount} шт.</b>',
        reply_markup=exclusive_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(lambda m: m.text == "📖 Коллекция")
async def collection(message: Message):
    register_user(message)
    unique, total = garage_summary(message.from_user.id)
    path = make_collection_cover()
    caption = (
        "📖 <b>МОЯ КОЛЛЕКЦИЯ</b>\n\n"
        f"🚘 Собрано: <b>{unique}/306</b>\n"
        f"📦 Всего экземпляров: <b>{total}</b>\n\n"
        "Нажми «Открыть коллекцию», чтобы смотреть машины с фотографиями."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🚘 Открыть коллекцию", callback_data="garage:all")
    kb.button(text="🏠 Гараж", callback_data="garage:all")
    kb.adjust(1)
    if path:
        await message.answer_photo(FSInputFile(path), caption=caption, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.message(lambda m: m.text == "🏠 Гараж")
async def garage(message: Message):
    unique, total = garage_summary(message.from_user.id)
    await message.answer(
        "🏠 <b>ТВОЙ ГАРАЖ</b>\n\n"
        f"🚗 Уникальных: <b>{unique}/306</b>\n"
        f"📦 Всего автомобилей: <b>{total}</b>\n\n"
        "Выбери раздел:",
        reply_markup=garage_keyboard(),
        parse_mode="HTML"
    )


async def show_garage_page(target, user_id, rarity=None, page=0, edit=False):
    items = get_garage(user_id, None if rarity == "all" else rarity)
    rarity_title = "Все машины" if rarity in (None, "all") else rarity

    if not items:
        text = (
            "🏠 <b>ГАРАЖ ПУСТ</b>\n\n"
            "У тебя пока нет машин этой категории.\n"
            "Открой кейс и начни коллекцию!"
        )
        markup = garage_keyboard()
    else:
        start = page * 8
        end = min(start + 8, len(items))
        lines = [
            f"🏠 <b>ГАРАЖ • {escape(rarity_title)}</b>",
            "",
            f"🚗 Машин в разделе: <b>{len(items)}</b>",
            ""
        ]
        for i, (car, amount) in enumerate(items[start:end], start=start + 1):
            lines.append(
                f'{i}. {RARITIES[car["rarity"]]["emoji"]} '
                f'<b>{escape(car["name"])}</b> ×{amount}'
            )
        lines.append("")
        lines.append("Нажми на машину, чтобы посмотреть характеристики.")
        text = "\n".join(lines)
        markup = garage_page_keyboard(items, page, None if rarity in (None, "all") else rarity)

    if edit:
        await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "garage_filters")
async def garage_filters(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔎 <b>ФИЛЬТР ГАРАЖА</b>\n\nВыбери редкость:",
        reply_markup=garage_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("garage:"))
async def garage_category(callback: CallbackQuery):
    rarity = callback.data.split(":", 1)[1]
    await show_garage_page(callback.message, callback.from_user.id, rarity, 0, edit=True)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("gpage:"))
async def garage_page(callback: CallbackQuery):
    _, rarity, page = callback.data.split(":")
    await show_garage_page(
        callback.message,
        callback.from_user.id,
        rarity,
        int(page),
        edit=True
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("car:"))
async def car_info(callback: CallbackQuery):
    car_id = int(callback.data.split(":")[1])
    car = CARS_BY_ID.get(car_id)

    if not car:
        await callback.answer("Машина не найдена.", show_alert=True)
        return

    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (callback.from_user.id, car_id)
        ).fetchone()

    if not row or row["amount"] <= 0:
        await callback.answer("Этой машины уже нет в гараже.", show_alert=True)
        return

    r = RARITIES[car["rarity"]]
    path = make_car_image(car)
    caption = car_caption(car, row["amount"]) + "\n" + f"💵 Продажа одной: <b>{money(int(car['price'] * r['sell']))}</b>"
    try:
        await callback.message.delete()
    except Exception:
        pass
    if path:
        await callback.message.answer_photo(FSInputFile(path), caption=caption, reply_markup=car_keyboard(car_id), parse_mode="HTML")
    else:
        await callback.message.answer(caption, reply_markup=car_keyboard(car_id), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("sell:"))
async def sell_one(callback: CallbackQuery):
    _, car_id, amount = callback.data.split(":")
    payout = sell_car(callback.from_user.id, int(car_id), int(amount))

    if payout <= 0:
        await callback.answer("Недостаточно экземпляров.", show_alert=True)
        return

    await callback.answer(f"Продано за {money(payout)}")

    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (callback.from_user.id, int(car_id))
        ).fetchone()

    if row and row["amount"] > 0:
        car = CARS_BY_ID[int(car_id)]
        r = RARITIES[car["rarity"]]
        await callback.message.edit_text(
            f'{r["emoji"]} <b>{escape(car["name"])}</b>\n\n'
            f'⭐ Редкость: <b>{escape(car["rarity"])}</b>\n'
            f'📅 Год выпуска: <b>{car["year"]}</b>\n'
            f'⚡ Мощность: <b>{car["power"]} л.с.</b>\n'
            f'💎 Стоимость: <b>{money(car["price"])}</b>\n'
            f'📦 В гараже: <b>{row["amount"]} шт.</b>\n'
            f'💵 Продажа одной: <b>{money(int(car["price"] * r["sell"]))}</b>',
            reply_markup=car_keyboard(int(car_id)),
            parse_mode="HTML"
        )
    else:
        await show_garage_page(
            callback.message,
            callback.from_user.id,
            "all",
            0,
            edit=True
        )


@dp.callback_query(lambda c: c.data.startswith("sellall:"))
async def sell_all(callback: CallbackQuery):
    car_id = int(callback.data.split(":")[1])
    with db() as conn:
        row = conn.execute(
            "SELECT amount FROM garage WHERE user_id=? AND car_id=?",
            (callback.from_user.id, car_id)
        ).fetchone()

    if not row:
        await callback.answer("Машины нет.", show_alert=True)
        return

    payout = sell_car(callback.from_user.id, car_id, row["amount"])
    await callback.answer(f"Продано: {money(payout)}")

    await show_garage_page(
        callback.message,
        callback.from_user.id,
        "all",
        0,
        edit=True
    )


@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@dp.message(lambda m: m.text == "📝 Квесты")
async def quests(message: Message):
    user = get_user(message.from_user.id)
    cases = min(user["cases_opened"], 3)
    await message.answer(
        "📝 <b>КВЕСТЫ</b>\n\n"
        f"1️⃣ Открой 3 кейса\n"
        f"Прогресс: <b>{cases}/3</b>\n"
        "🎁 Награда: 500 000$\n\n"
        "2️⃣ Собери Rare автомобиль\n"
        "Прогресс: смотри гараж 🔵\n"
        "🎁 Награда: 1 000 000$\n\n"
        "3️⃣ Пригласи друга\n"
        "Прогресс: 0/1\n"
        "🎁 Награда: 750 000$",
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🏆 Сезон")
async def season(message: Message):
    register_user(message)
    user = get_user(message.from_user.id)
    path = make_season_image()
    level = user["xp"] // 1000 + 1
    caption = (
        "🏆 <b>СЕЗОН 1</b>\n\n"
        f"⭐ Твой уровень: <b>{level}</b>\n"
        f"✨ Твой XP: <b>{user['xp']}</b>\n\n"
        "🎁 За открытие кейса: +100 XP\n"
        "🏅 Чем больше XP — тем выше место в рейтинге."
    )
    if path:
        await message.answer_photo(FSInputFile(path), caption=caption, parse_mode="HTML")
    else:
        await message.answer(caption, parse_mode="HTML")


@dp.message(lambda m: m.text == "🎁 Промокод")
async def promo(message: Message):
    await message.answer(
        "🎁 <b>ПРОМОКОД</b>\n\n"
        "Чтобы активировать код, отправь сообщение:\n"
        "<code>/promo КОД</code>",
        parse_mode="HTML"
    )


PROMOCODES = {
    "START": {"balance": 1_000_000, "xp": 100},
    "ZONA": {"balance": 2_000_000, "xp": 250},
}


@dp.message(lambda m: (m.text or "").startswith("/promo "))
async def promo_activate(message: Message):
    code = message.text.split(maxsplit=1)[1].strip().upper()
    reward = PROMOCODES.get(code)
    if not reward:
        await message.answer("❌ Промокод не найден или уже недействителен.")
        return
    ensure_user(message.from_user.id)
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS used_promocodes (user_id INTEGER, code TEXT, PRIMARY KEY(user_id, code))")
        try:
            conn.execute("INSERT INTO used_promocodes(user_id, code) VALUES (?, ?)", (message.from_user.id, code))
        except sqlite3.IntegrityError:
            await message.answer("⚠️ Ты уже использовал этот промокод.")
            return
        conn.execute("UPDATE users SET balance=balance+?, xp=xp+? WHERE user_id=?", (reward["balance"], reward["xp"], message.from_user.id))
    await message.answer(f"✅ Промокод активирован!\n\n💰 +{money(reward['balance'])}\n⭐ +{reward['xp']} XP")


@dp.message(lambda m: m.text == "👥 Реферальная ссылка")
async def referral(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    await message.answer(
        "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"🔗 Твоя ссылка:\n<code>https://t.me/ZonaCarCaseBot?start={user_id}</code>\n\n"
        f"👤 Приглашено: <b>{user['referrals']}</b>\n"
        f"💰 Заработано: <b>{money(user['referral_earnings'])}</b>\n\n"
        "🎁 За нового игрока: 500 000$ + 100 XP",
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🎁 Ежедневный бонус")
async def daily_bonus(message: Message):
    if claim_daily(message.from_user.id):
        await message.answer("🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС ПОЛУЧЕН!</b>\n\n💰 +500 000$\n⭐ +50 XP", parse_mode="HTML")
    else:
        await message.answer("⏳ Ты уже забрал ежедневный бонус. Возвращайся завтра!")


@dp.callback_query(lambda c: c.data == "back_menu")
async def back_menu(callback: CallbackQuery):
    await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\nВыбери действие через кнопки ниже.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# =========================================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER
# =========================================================
def run_web_server():
    port = int(os.environ.get("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot is running!")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("0.0.0.0", port), Handler)
    logging.info("WEB SERVER: listening on 0.0.0.0:%s", port)
    server.serve_forever()


# =========================================================
# ЗАПУСК
# =========================================================
async def main():
    logging.basicConfig(level=logging.INFO)

    if not TOKEN:
        raise RuntimeError(
            "Не найден BOT_TOKEN. В CMD выполни: set BOT_TOKEN=ТВОЙ_НОВЫЙ_ТОКЕН"
        )

    init_db()
    logging.info("Загружено автомобилей: %s", len(CARS))
    logging.info("База: %s", os.path.abspath(DB_FILE))

    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    if not get_auction():
        start_new_auction()
    asyncio.create_task(auction_loop(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
