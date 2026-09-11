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


class ClanCreateState(StatesGroup):
    name = State()



# =========================================================
# НАСТРОЙКИ
# =========================================================
# ВАЖНО: не вставляй токен прямо в код.
# Перед запуском в CMD выполни:
# set BOT_TOKEN="ТВОЙ_ТОКЕН"
TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = os.getenv("DB_FILE", os.path.join(os.getcwd(), "zonacarcase.db"))
CASE_PRICE = 1_200_000
CASE_COOLDOWN = 3 * 60 * 60  # 3 часа
AUCTION_INTERVAL = 60 * 60  # новый лот каждый час
AUCTION_BID_TIME = 60  # 1 минута после каждой ставки
AUCTION_MIN_BID = 1_000_000
AUCTION_BID_STEP = 500_000
ADMIN_ID = 5474546385

# Кланы
CLAN_CREATE_PRICE = 5_000_000
CLAN_MAX_MEMBERS = 20
CLAN_NAME_MIN = 3
CLAN_NAME_MAX = 24

# Автомобильные номера
# Равный шанс выпадения каждой страны: РФ / Украина / Беларусь / Казахстан.
PLATE_COUNTRIES = ("🇷🇺 РФ", "🇺🇦 УКРАИНА", "🇧🇾 БЕЛАРУСЬ", "🇰🇿 КАЗАХСТАН")
RU_PLATE_LETTERS = "АВЕКМНОРСТУХ"  # разрешённый набор букв для обычных РФ номеров
UA_PLATE_LETTERS = "АВСЕНІКМОРТХ"  # буквы украинских знаков с латинскими графическими аналогами
BY_PLATE_LETTERS = "ABCEHKMOPTX"
KZ_PLATE_LETTERS = "ABCEHKMOPTX"
RU_REGION_CODES = [
    "01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16","17","18","19","20",
    "21","22","23","24","25","26","27","28","29","30","31","32","33","34","35","36","37","38","39","40",
    "41","42","43","44","45","46","47","48","49","50","51","52","53","54","55","56","57","58","59","60",
    "61","62","63","64","65","66","67","68","69","70","71","72","73","74","75","76","77","78","79","80",
    "81","82","83","84","85","86","87","89","90","91","92","93","94","95","96","97","98","99",
    "102","116","121","122","123","124","125","126","134","136","138","142","147","150","152","154","156","159","161","163","164","169","172","173","174","176","177","178","180","181","182","186","188","190","193","196","197","198","199","750","777","790","797","799","977","977"
]
UA_REGION_CODES = [
    "AA","AB","AC","AE","AH","AI","AK","AM","AO","AP","AT","AX",
    "BA","BB","BC","BE","BH","BI","BK","BM","BO","BT","BX",
    "CA","CE","CH","CK","CM","CO","CP","CT","CX",
    "HA","HB","HC","HE","HH","HI","HK","HM","HO","HT","HX",
    "IA","IB","IC","IE","IH","II","IK","IM","IO","IP","IT","IX"
]
BY_REGION_CODES = ["1","2","3","4","5","6","7"]
KZ_REGION_CODES = [f"{i:02d}" for i in range(1, 21)]

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

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Exclusive", "Secret"]

# Система из 100 уровней. Уровень определяется по накопленному XP.
# Порог XP растёт по формуле: 250 * (уровень - 1)^2.
# Поэтому 100-й уровень требует 2 450 250 XP.
LEVELS = [
    (1, 0, "Новичок"),
    (2, 250, "Новичок"),
    (3, 1000, "Новичок"),
    (4, 2250, "Новичок"),
    (5, 4000, "Новичок"),
    (6, 6250, "Ученик"),
    (7, 9000, "Ученик"),
    (8, 12250, "Ученик"),
    (9, 16000, "Ученик"),
    (10, 20250, "Ученик"),
    (11, 25000, "Любитель"),
    (12, 30250, "Любитель"),
    (13, 36000, "Любитель"),
    (14, 42250, "Любитель"),
    (15, 49000, "Любитель"),
    (16, 56250, "Игрок"),
    (17, 64000, "Игрок"),
    (18, 72250, "Игрок"),
    (19, 81000, "Игрок"),
    (20, 90250, "Игрок"),
    (21, 100000, "Автолюбитель"),
    (22, 110250, "Автолюбитель"),
    (23, 121000, "Автолюбитель"),
    (24, 132250, "Автолюбитель"),
    (25, 144000, "Автолюбитель"),
    (26, 156250, "Водитель"),
    (27, 169000, "Водитель"),
    (28, 182250, "Водитель"),
    (29, 196000, "Водитель"),
    (30, 210250, "Водитель"),
    (31, 225000, "Гонщик"),
    (32, 240250, "Гонщик"),
    (33, 256000, "Гонщик"),
    (34, 272250, "Гонщик"),
    (35, 289000, "Гонщик"),
    (36, 306250, "Коллекционер"),
    (37, 324000, "Коллекционер"),
    (38, 342250, "Коллекционер"),
    (39, 361000, "Коллекционер"),
    (40, 380250, "Коллекционер"),
    (41, 400000, "Продвинутый"),
    (42, 420250, "Продвинутый"),
    (43, 441000, "Продвинутый"),
    (44, 462250, "Продвинутый"),
    (45, 484000, "Продвинутый"),
    (46, 506250, "Профи"),
    (47, 529000, "Профи"),
    (48, 552250, "Профи"),
    (49, 576000, "Профи"),
    (50, 600250, "Профи"),
    (51, 625000, "Эксперт"),
    (52, 650250, "Эксперт"),
    (53, 676000, "Эксперт"),
    (54, 702250, "Эксперт"),
    (55, 729000, "Эксперт"),
    (56, 756250, "Мастер"),
    (57, 784000, "Мастер"),
    (58, 812250, "Мастер"),
    (59, 841000, "Мастер"),
    (60, 870250, "Мастер"),
    (61, 900000, "Ветеран"),
    (62, 930250, "Ветеран"),
    (63, 961000, "Ветеран"),
    (64, 992250, "Ветеран"),
    (65, 1024000, "Ветеран"),
    (66, 1056250, "Чемпион"),
    (67, 1089000, "Чемпион"),
    (68, 1122250, "Чемпион"),
    (69, 1156000, "Чемпион"),
    (70, 1190250, "Чемпион"),
    (71, 1225000, "Элита"),
    (72, 1260250, "Элита"),
    (73, 1296000, "Элита"),
    (74, 1332250, "Элита"),
    (75, 1369000, "Элита"),
    (76, 1406250, "Легенда"),
    (77, 1444000, "Легенда"),
    (78, 1482250, "Легенда"),
    (79, 1521000, "Легенда"),
    (80, 1560250, "Легенда"),
    (81, 1600000, "Миф"),
    (82, 1640250, "Миф"),
    (83, 1681000, "Миф"),
    (84, 1722250, "Миф"),
    (85, 1764000, "Миф"),
    (86, 1806250, "Король дорог"),
    (87, 1849000, "Король дорог"),
    (88, 1892250, "Король дорог"),
    (89, 1936000, "Король дорог"),
    (90, 1980250, "Король дорог"),
    (91, 2025000, "Император дорог"),
    (92, 2070250, "Император дорог"),
    (93, 2116000, "Император дорог"),
    (94, 2162250, "Император дорог"),
    (95, 2209000, "Император дорог"),
    (96, 2256250, "Бог автомобилей"),
    (97, 2304000, "Бог автомобилей"),
    (98, 2352250, "Бог автомобилей"),
    (99, 2401000, "Бог автомобилей"),
    (100, 2450250, "Бог автомобилей"),
]

def get_level_info(xp):
    """Возвращает (уровень, название, XP_текущего_уровня, XP_до_следующего, прогресс_%) ."""
    xp = max(0, int(xp or 0))
    current = LEVELS[0]
    next_level = None
    for item in LEVELS:
        if xp >= item[1]:
            current = item
        else:
            next_level = item
            break

    level, start_xp, title = current
    if next_level:
        next_xp = next_level[1]
        progress = int((xp - start_xp) / max(1, next_xp - start_xp) * 100)
    else:
        next_xp = None
        progress = 100
    return level, title, start_xp, next_xp, min(100, max(0, progress))

def level_bar(progress, size=10):
    filled = round(size * progress / 100)
    return "🟩" * filled + "⬜" * (size - filled)

# Все автомобили добавляются вручную через админ-панель.
# В файле нет предзаполненного списка машин.

CARS = []
CARS_BY_ID = {}
CARS_BY_RARITY = {rarity: [] for rarity in RARITY_ORDER}

# =========================================================
# DATABASE / V2
# =========================================================

def db():
    # SQLite сохраняется между переподключениями бота: переподключение Telegram
    # не пересоздаёт базу и не удаляет данные игроков/машины.
    conn = sqlite3.connect(DB_FILE, timeout=30)

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
            CREATE TABLE IF NOT EXISTS clans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                owner_id INTEGER NOT NULL,
                created_at REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clan_members (
                clan_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (clan_id, user_id)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                country TEXT NOT NULL,
                plate TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL DEFAULT 0
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


def _rand_letters(alphabet, count):
    return "".join(random.choice(alphabet) for _ in range(count))


def generate_random_plate(country=None):
    """Генерирует случайный гражданский номер одной из 4 стран."""
    country = country or random.choice(PLATE_COUNTRIES)
    if country == "🇷🇺 РФ":
        # Формат: X000XX + код региона.
        return f"{random.choice(RU_PLATE_LETTERS)}{random.randint(0,999):03d}{_rand_letters(RU_PLATE_LETTERS,2)} {random.choice(RU_REGION_CODES)}", country
    if country == "🇺🇦 УКРАИНА":
        # Формат: AA 1234 AA.
        return f"{_rand_letters(UA_PLATE_LETTERS,2)} {random.randint(0,9999):04d} {_rand_letters(UA_PLATE_LETTERS,2)}", country
    if country == "🇧🇾 БЕЛАРУСЬ":
        # Формат: 1234 AB-7.
        return f"{random.randint(0,9999):04d} {_rand_letters(BY_PLATE_LETTERS,2)}-{random.choice(BY_REGION_CODES)}", country
    # Казахстан: 123 ABC 01.
    return f"{random.randint(1,999):03d} {_rand_letters(KZ_PLATE_LETTERS,3)} {random.choice(KZ_REGION_CODES)}", country


def give_random_plate(user_id):
    """Выдаёт уникальный случайный номер и сохраняет его в БД."""
    for _ in range(100):
        plate, country = generate_random_plate()
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO plates(user_id,country,plate,created_at) VALUES(?,?,?,?)",
                    (user_id, country, plate, time.time())
                )
            return country, plate
        except sqlite3.IntegrityError:
            continue
    # Крайне маловероятный fallback.
    with db() as conn:
        plate, country = generate_random_plate()
        conn.execute(
            "INSERT INTO plates(user_id,country,plate,created_at) VALUES(?,?,?,?)",
            (user_id, country, plate + "*", time.time())
        )
    return country, plate + "*"


def get_user_plates(user_id, limit=10):
    with db() as conn:
        return conn.execute(
            "SELECT country, plate, created_at FROM plates WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()


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
    # Загружаются только машины, добавленные через админ-панель.
    CARS = custom
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


# =========================================================
# CLANS
# =========================================================

def get_user_clan(user_id):
    """Возвращает клан игрока или None."""
    with db() as conn:
        return conn.execute("""
            SELECT c.*, cm.role
            FROM clan_members cm
            JOIN clans c ON c.id = cm.clan_id
            WHERE cm.user_id=?
        """, (user_id,)).fetchone()


def get_clan_member_count(clan_id):
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM clan_members WHERE clan_id=?", (clan_id,)).fetchone()
    return int(row["cnt"])


def get_clan_members(clan_id):
    with db() as conn:
        return conn.execute("""
            SELECT cm.user_id, cm.role, cm.joined_at, u.username, u.first_name, u.xp, u.balance
            FROM clan_members cm
            LEFT JOIN users u ON u.user_id = cm.user_id
            WHERE cm.clan_id=?
            ORDER BY CASE WHEN cm.role='owner' THEN 0 ELSE 1 END, u.xp DESC, cm.joined_at ASC
        """, (clan_id,)).fetchall()


def get_clan_by_id(clan_id):
    with db() as conn:
        return conn.execute("SELECT * FROM clans WHERE id=?", (clan_id,)).fetchone()


def create_clan(owner_id, name):
    name = " ".join(name.strip().split())
    if not (CLAN_NAME_MIN <= len(name) <= CLAN_NAME_MAX):
        return False, "❌ Название клана должно быть от 3 до 24 символов."
    if any(ord(ch) < 32 for ch in name):
        return False, "❌ Некорректное название клана."
    ensure_user(owner_id)
    with db() as conn:
        existing = conn.execute("SELECT id FROM clan_members WHERE user_id=?", (owner_id,)).fetchone()
        if existing:
            return False, "❌ Ты уже состоишь в клане. Сначала выйди из текущего клана."
        duplicate = conn.execute("SELECT id FROM clans WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        if duplicate:
            return False, "❌ Клан с таким названием уже существует."
        user = conn.execute("SELECT balance FROM users WHERE user_id=?", (owner_id,)).fetchone()
        if not user or user["balance"] < CLAN_CREATE_PRICE:
            return False, f"❌ Для создания клана нужно {money(CLAN_CREATE_PRICE)}."
        now = time.time()
        cur = conn.execute("INSERT INTO clans(name, owner_id, created_at) VALUES(?,?,?)", (name, owner_id, now))
        clan_id = cur.lastrowid
        conn.execute("INSERT INTO clan_members(clan_id,user_id,role,joined_at) VALUES(?,?,?,?)", (clan_id, owner_id, "owner", now))
        conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (CLAN_CREATE_PRICE, owner_id))
    return get_clan_by_id(clan_id), None


def join_clan(user_id, clan_id):
    ensure_user(user_id)
    with db() as conn:
        clan = conn.execute("SELECT * FROM clans WHERE id=?", (clan_id,)).fetchone()
        if not clan:
            return False, "❌ Клан не найден."
        existing = conn.execute("SELECT clan_id FROM clan_members WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            if existing["clan_id"] == clan_id:
                return False, "⚠️ Ты уже в этом клане."
            return False, "❌ Ты уже состоишь в другом клане."
        count = conn.execute("SELECT COUNT(*) AS cnt FROM clan_members WHERE clan_id=?", (clan_id,)).fetchone()["cnt"]
        if count >= CLAN_MAX_MEMBERS:
            return False, f"❌ Клан заполнен. Максимум: {CLAN_MAX_MEMBERS} участников."
        conn.execute("INSERT INTO clan_members(clan_id,user_id,role,joined_at) VALUES(?,?,?,?)", (clan_id, user_id, "member", time.time()))
    return True, None


def leave_clan(user_id):
    with db() as conn:
        row = conn.execute("SELECT clan_id, role FROM clan_members WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return False, "❌ Ты не состоишь в клане."
        if row["role"] == "owner":
            return False, "👑 Владелец не может просто выйти. Передай клан другому игроку или расформируй его."
        conn.execute("DELETE FROM clan_members WHERE user_id=?", (user_id,))
    return True, None


def disband_clan(owner_id):
    with db() as conn:
        clan = conn.execute("SELECT * FROM clans WHERE owner_id=?", (owner_id,)).fetchone()
        if not clan:
            return False, "❌ Ты не являешься владельцем клана."
        conn.execute("DELETE FROM clan_members WHERE clan_id=?", (clan["id"],))
        conn.execute("DELETE FROM clans WHERE id=?", (clan["id"],))
    return True, None


def kick_clan_member(owner_id, target_id):
    with db() as conn:
        clan = conn.execute("SELECT * FROM clans WHERE owner_id=?", (owner_id,)).fetchone()
        if not clan:
            return False, "❌ Только владелец может исключать участников."
        target = conn.execute("SELECT role FROM clan_members WHERE clan_id=? AND user_id=?", (clan["id"], target_id)).fetchone()
        if not target:
            return False, "❌ Игрок не найден в твоём клане."
        if target["role"] == "owner":
            return False, "❌ Нельзя исключить владельца."
        conn.execute("DELETE FROM clan_members WHERE clan_id=? AND user_id=?", (clan["id"], target_id))
    return True, None


def clan_player_name(row):
    if row["username"]:
        return "@" + row["username"]
    if row["first_name"]:
        return row["first_name"]
    return f"ID {row['user_id']}"


def clan_list_text():
    with db() as conn:
        clans = conn.execute("""
            SELECT c.id, c.name, c.owner_id, COUNT(cm.user_id) AS members
            FROM clans c
            LEFT JOIN clan_members cm ON cm.clan_id=c.id
            GROUP BY c.id
            ORDER BY members DESC, c.created_at ASC
            LIMIT 10
        """).fetchall()
    if not clans:
        return "💀 <b>КЛАНЫ</b>\n\nПока нет ни одного клана. Создай первый!", []
    lines = ["💀 <b>КЛАНЫ</b>", "", "🏆 <b>ТОП КЛАНОВ</b>", ""]
    for i, clan in enumerate(clans, 1):
        lines.append(f"{i}. 💀 <b>{escape(clan['name'])}</b> — {clan['members']}/{CLAN_MAX_MEMBERS}")
    return "\n".join(lines), clans


def clans_keyboard():
    kb = InlineKeyboardBuilder()
    with db() as conn:
        clans = conn.execute("""
            SELECT c.id, c.name, COUNT(cm.user_id) AS members
            FROM clans c LEFT JOIN clan_members cm ON cm.clan_id=c.id
            GROUP BY c.id ORDER BY members DESC, c.created_at ASC LIMIT 10
        """).fetchall()
    for clan in clans:
        kb.button(text=f"💀 {clan['name']} • {clan['members']}/{CLAN_MAX_MEMBERS}", callback_data=f"clan:view:{clan['id']}")
    kb.button(text="➕ Создать клан", callback_data="clan:create")
    kb.button(text="🔄 Обновить", callback_data="clan:list")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def clan_view_keyboard(clan_id, user_id):
    kb = InlineKeyboardBuilder()
    my_clan = get_user_clan(user_id)
    if my_clan and my_clan["id"] == clan_id:
        kb.button(text="👥 Участники", callback_data=f"clan:members:{clan_id}")
        if my_clan["role"] == "owner":
            kb.button(text="🗑 Расформировать", callback_data="clan:disband")
        else:
            kb.button(text="🚪 Выйти из клана", callback_data="clan:leave")
    elif not my_clan:
        kb.button(text="✅ Вступить", callback_data=f"clan:join:{clan_id}")
    kb.button(text="⬅️ Кланы", callback_data="clan:list")
    kb.adjust(1)
    return kb.as_markup()


def my_clan_keyboard(user_id):
    clan = get_user_clan(user_id)
    kb = InlineKeyboardBuilder()
    if not clan:
        kb.button(text="💀 Найти клан", callback_data="clan:list")
        kb.button(text="➕ Создать клан", callback_data="clan:create")
    else:
        kb.button(text="👥 Участники", callback_data=f"clan:members:{clan['id']}")
        if clan["role"] == "owner":
            kb.button(text="🗑 Расформировать", callback_data="clan:disband")
        else:
            kb.button(text="🚪 Выйти из клана", callback_data="clan:leave")
        kb.button(text="💀 Клан", callback_data=f"clan:view:{clan['id']}")
    kb.button(text="🏠 Меню", callback_data="back_menu")
    kb.adjust(1)
    return kb.as_markup()


def clan_members_keyboard(clan, user_id):
    kb = InlineKeyboardBuilder()
    if clan["owner_id"] == user_id:
        members = get_clan_members(clan["id"])
        for m in members:
            if m["user_id"] != user_id:
                kb.button(text=f"❌ Исключить {clan_player_name(m)}", callback_data=f"clan:kick:{m['user_id']}")
    kb.button(text="⬅️ Клан", callback_data=f"clan:view:{clan['id']}")
    kb.adjust(1)
    return kb.as_markup()


def clan_text(clan):
    members = get_clan_members(clan["id"])
    owner = next((m for m in members if m["role"] == "owner"), None)
    total_xp = sum(int(m["xp"] or 0) for m in members)
    return (
        f"💀 <b>КЛАН «{escape(clan['name'])}»</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👑 Владелец: <b>{escape(clan_player_name(owner)) if owner else '—'}</b>\n"
        f"👥 Участники: <b>{len(members)}/{CLAN_MAX_MEMBERS}</b>\n"
        f"⭐ Общий XP: <b>{total_xp}</b>\n"
        f"📅 Создан: <b>{time.strftime('%d.%m.%Y', time.localtime(clan['created_at']))}</b>\n\n"
        "🎯 Цель клана — собирать коллекцию, развивать аккаунты и подниматься в топе."
    )


def clan_members_text(clan):
    members = get_clan_members(clan["id"])
    lines = [f"👥 <b>УЧАСТНИКИ «{escape(clan['name'])}»</b>", ""]
    for i, m in enumerate(members, 1):
        role = "👑" if m["role"] == "owner" else "👤"
        lines.append(f"{i}. {role} <b>{escape(clan_player_name(m))}</b> — {m['xp']} XP")
    return "\n".join(lines)


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
    return f"{int(value):,}".replace(",", " ") + "$"


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"


def choose_car():
    available = [r for r in RARITY_ORDER if CARS_BY_RARITY.get(r)]
    if not available:
        return None
    rarity = random.choices(available, weights=[RARITIES[r]["chance"] for r in available], k=1)[0]
    return random.choice(CARS_BY_RARITY[rarity])


def choose_container_car(container_id):
    c = CONTAINERS[container_id]
    available = [r for r in c["rarities"] if CARS_BY_RARITY.get(r)]
    if not available:
        return None
    rarity = random.choice(available)
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
    if not CARS_BY_RARITY.get("Exclusive"):
        return None
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
    """Главная клавиатура в стиле референса: 6 больших кнопок 2x3."""
    kb = ReplyKeyboardBuilder()
    for text in [
        "🔢 Получить номер", "🚘 Получить тачку",
        "📋 Меню", "🗂 Коллекция",
        "💀 Кланы", "💀 Мой клан",
    ]:
        kb.button(text=text)
    kb.adjust(2, 2, 2)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def extended_menu_keyboard():
    """Главное меню в стиле референса PLATE: 2 колонки."""
    kb = ReplyKeyboardBuilder()
    for text in [
        "🎁 Маркет", "🔥 Лимитки",
        "🎟 Билеты", "🎯 Сезонная сетка",
        "💀 Кланы", "🔫 Лут",
        "💵 На учёт", "🏎 Тюнинг",
        "🚙 Концепты", "🔄 Обмены",
        "🏆 Лидеры", "📱 Профиль",
        "🔢 Коллекция номеров", "🗂 Коллекция",
        "🔙 Назад",
    ]:
        kb.button(text=text)
    kb.adjust(2, 2, 2, 2, 2, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


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


def collection_keyboard(user_id, page=0, total=0):
    """Меню коллекции в стиле референса PLATE."""
    kb = InlineKeyboardBuilder()
    total_pages = max(1, total)
    page = max(0, min(page, total_pages - 1))

    kb.button(text="⏮", callback_data="collection:page:0")
    kb.button(text="◀️", callback_data=f"collection:page:{max(0, page-1)}")
    kb.button(text=f"{page+1}/{total_pages}", callback_data="noop")
    kb.button(text="▶️", callback_data=f"collection:page:{min(total_pages-1, page+1)}")
    kb.button(text="⏭", callback_data=f"collection:page:{total_pages-1}")

    # Счётчик машин в коллекции. Кнопки оставлены как отдельные действия,
    # чтобы интерфейс был таким же, как на референсе.
    owned_total = get_total_garage_amount(user_id)
    kb.button(text="➖", callback_data="collection:minus")
    kb.button(text=f"{owned_total}/20", callback_data="collection:count")
    kb.button(text="➕", callback_data="collection:plus")

    kb.button(text="💎 Редкость", callback_data="collection:rarity")
    kb.button(text="🏷 Бренд", callback_data="collection:brand")
    kb.button(text="🔢 Учет", callback_data="collection:accounting")
    kb.button(text="🟪 Дубли", callback_data="collection:duplicates")
    kb.button(text="🍂 Сезоны", callback_data="collection:seasons")
    kb.button(text="🔎 Поиск", callback_data="collection:search")
    kb.button(text="🚫 Выбрано", callback_data="collection:selected")
    kb.button(text="🚫 Фильтры", callback_data="collection:filters")
    kb.button(text="❌ Скрыть авто в коллекциях", callback_data="collection:hide")
    kb.button(text="🔙 Назад", callback_data="back_menu")
    kb.adjust(5, 3, 2, 2, 2, 2, 1, 1)
    return kb.as_markup()


def number_collection_keyboard(user_id, page=0, total=0):
    """Коллекция номеров в стиле референса PLATE."""
    kb = InlineKeyboardBuilder()
    total_pages = max(1, total)
    page = max(0, min(page, total_pages - 1))
    owned_count = len(get_user_plates(user_id, 100000))

    # Навигация по номерам
    kb.button(text="⏮", callback_data="plates:page:0")
    kb.button(text="◀️", callback_data=f"plates:page:{max(0, page-1)}")
    kb.button(text=f"{page+1}/{total_pages}", callback_data="plates:noop")
    kb.button(text="▶️", callback_data=f"plates:page:{min(total_pages-1, page+1)}")
    kb.button(text="⏭", callback_data=f"plates:page:{total_pages-1}")

    # Счётчик коллекции
    kb.button(text="➖", callback_data="plates:minus")
    kb.button(text=str(owned_count), callback_data="plates:count")
    kb.button(text="➕", callback_data="plates:plus")

    # Фильтры как на референсе
    kb.button(text="🌍 Страна", callback_data="plates:country")
    kb.button(text="🏷 Тип", callback_data="plates:type")
    kb.button(text="🔢 Учет", callback_data="plates:accounting")
    kb.button(text="📦 Дубликаты", callback_data="plates:duplicates")
    kb.button(text="🔎 Поиск", callback_data="plates:search")
    kb.button(text="📊 Фильтры", callback_data="plates:filters")
    kb.button(text="❌ Скрыть уже имеющиеся", callback_data="plates:hide")
    kb.button(text="🔙 Назад", callback_data="back_menu")
    kb.adjust(5, 3, 2, 2, 2, 1, 1)
    return kb.as_markup()


async def show_number_collection(message, user_id, page=0, edit=False):
    """Открывает коллекцию номеров в формате, максимально близком к референсу PLATE."""
    plates = get_user_plates(user_id, 100000)
    total = len(plates)

    # В шапке коллекции показываем только сводку и активные фильтры,
    # как на референсе. Подробная информация о номере открывается
    # отдельным нажатием/перелистыванием.
    text = (
        "📦 <b>Коллекция номеров</b>\n"
        f"📄 У вас уже есть: <b>{total}</b> номеров\n"
        "────────────────────\n"
        "📌 <b>Доступные фильтры:</b>\n"
        "🌍 Страна: <b>Все</b>\n"
        "🏷 Тип: <b>Все</b>\n"
        "🔢 Учет: <b>Все</b>\n"
        "📦 Дубликаты: <b>Все</b>\n"
        "🔎 Поиск: <b>Выкл</b>\n"
        "📊 Фильтры: <b>Выкл</b>\n"
        "────────────────────\n"
        "ℹ️ Выберите номер, чтобы посмотреть подробную информацию"
    )

    # Даже при пустой коллекции оставляем интерфейс и пагинацию доступными.
    markup = number_collection_keyboard(user_id, page if total else 0, total if total else 1)
    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


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


def get_total_garage_amount(user_id):
    with db() as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM garage WHERE user_id=?", (user_id,)).fetchone()
        return int(row["total"] if row else 0)


def get_collection_items(user_id):
    return get_garage(user_id, None)


async def show_collection(message, user_id, page=0, edit=False):
    """Показывает коллекцию по одной машине с навигацией как на референсе."""
    items = get_collection_items(user_id)
    if not items:
        text = (
            "🗂 <b>КОЛЛЕКЦИЯ</b>\n\n"
            "У тебя пока нет машин.\n"
            "Открой кейс, чтобы получить первую машину!"
        )
        markup = collection_keyboard(user_id, 0, 1)
        if edit:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
        return

    page = max(0, min(page, len(items)-1))
    car, amount = items[page]
    r = RARITIES[car["rarity"]]
    text = (
        f"🗂 <b>КОЛЛЕКЦИЯ</b>\n\n"
        f"🚘 <b>{escape(car['name'])}</b>\n"
        f"{r['emoji']} Редкость: <b>{escape(car['rarity'])}</b>\n"
        f"📅 Год: <b>{car['year']}</b>\n"
        f"⚡ Мощность: <b>{car['power']} л.с.</b>\n"
        f"💰 Цена: <b>{money(car['price'])}</b>\n"
        f"📦 Кол-во: <b>{amount} шт.</b>\n\n"
        f"🚘 Машина <b>{page+1}</b> из <b>{len(items)}</b>"
    )
    markup = collection_keyboard(user_id, page, len(items))
    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


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


MENU_STUBS = {
    "🎁 Маркет": "🎁 <b>МАРКЕТ</b>\n\nРаздел маркета пока находится в разработке.",
    "🔥 Лимитки": "🔥 <b>ЛИМИТКИ</b>\n\nЗдесь будут редкие лимитированные машины и предметы.",
    "🎟 Билеты": "🎟 <b>БИЛЕТЫ</b>\n\nЗдесь будут твои билеты и доступные награды.",
    "🎯 Сезонная сетка": "🎯 <b>СЕЗОННАЯ СЕТКА</b>\n\nЗдесь будет прогресс сезонных заданий и наград.",
    "🔫 Лут": "🔫 <b>ЛУТ</b>\n\nЗдесь будет раздел с полученными предметами и наградами.",
    "💵 На учёт": "💵 <b>НА УЧЁТ</b>\n\nЗдесь будет постановка автомобилей на учёт.",
    "🏎 Тюнинг": "🏎 <b>ТЮНИНГ</b>\n\nЗдесь будет настройка и улучшение автомобилей.",
    "🚙 Концепты": "🚙 <b>КОНЦЕПТЫ</b>\n\nЗдесь будут концептуальные автомобили.",
    "🔄 Обмены": "🔄 <b>ОБМЕНЫ</b>\n\nЗдесь будет обмен автомобилями и номерами между игроками.",
}

for _menu_text, _menu_text_response in MENU_STUBS.items():
    @dp.message(lambda m, t=_menu_text: m.text == t)
    async def _menu_stub(message: Message, response=_menu_text_response):
        await message.answer(response, reply_markup=extended_menu_keyboard(), parse_mode="HTML")


@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(message: Message):
    user = get_user(message.from_user.id)
    unique, total = garage_summary(message.from_user.id)
    level, title, start_xp, next_xp, progress = get_level_info(user["xp"])
    xp_bar = level_bar(progress)
    current_xp = max(0, int(user["xp"]) - start_xp)
    level_goal = (str(next_xp) if next_xp is not None else "MAX")
    await message.answer(
        "👤 <b>ТВОЙ ПРОФИЛЬ</b>\n━━━━━━━━━━━━━━\n\n"
        f"💰 Баланс: <b>{money(user['balance'])}</b>\n"
        f"🏆 Уровень: <b>{level} — {title}</b>\n{xp_bar} <b>{current_xp} XP</b> → <b>{level_goal}</b>\n\n"
        f"🚘 Уникальных: <b>{unique}/{len(CARS)}</b>\n📦 Всего машин: <b>{total}</b>\n"
        f"🔢 Номеров: <b>{len(get_user_plates(message.from_user.id, 100000))}</b>\n"
        f"🎁 Открыто кейсов: <b>{user['cases_opened']}</b>\n"
        f"👥 Рефералов: <b>{user['referrals']}</b>\n"
        f"💸 Заработано с рефералов: <b>{money(user['referral_earned'])}</b>",
        parse_mode="HTML"
    )

# =========================================================
# REFERENCE MAIN BUTTONS
# =========================================================

@dp.message(lambda m: m.text == "🔢 Получить номер")
async def get_number_button(message: Message):
    country, plate = give_random_plate(message.from_user.id)
    total = 0
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM plates WHERE user_id=?", (message.from_user.id,)).fetchone()
        total = int(row["cnt"])
    await message.answer(
        "🎉 <b>ТЕБЕ ВЫПАЛ НОВЫЙ НОМЕР!</b>\n\n"
        f"🌍 Страна: <b>{escape(country)}</b>\n"
        f"🚘 Номер: <code>{escape(plate)}</code>\n\n"
        f"📦 Всего твоих номеров: <b>{total}</b>\n\n"
        "Нажми «🔢 Получить номер» ещё раз — выпадет новый случайный номер.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


@dp.message(lambda m: m.text == "🚘 Получить тачку")
async def get_car_button(message: Message):
    # Та же механика, что и у старой кнопки «🚘 Открыть авто».
    await open_auto(message)


@dp.message(lambda m: m.text == "📋 Меню")
async def reference_menu(message: Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    user = get_user(user_id)
    unique, total = garage_summary(user_id)
    plate_count = len(get_user_plates(user_id, 100000))
    level, title, start_xp, next_xp, progress = get_level_info(user["xp"])
    bar = level_bar(progress)

    now = time.time()
    remaining = max(0, CASE_COOLDOWN - (now - (user["last_case_opened"] or 0)))
    next_case = "готов" if remaining <= 0 else fmt_time(remaining)

    # Сезон и ключи пока не имеют отдельных игровых таблиц, поэтому показываем
    # реальные доступные данные без выдумывания значений.
    streak = int(user["daily_streak"] or 0)
    username = message.from_user.username or user["username"] or str(user_id)
    clan = get_user_clan(user_id)
    clan_name = clan["name"] if clan else "Нет клана"

    text = (
        "🛠 <b>ПАНЕЛЬ УПРАВЛЕНИЯ:</b>\n\n"
        f"👤 <b>Логин:</b> <code>{escape(username)}</code>\n"
        f"🎯 <b>Сезонная сетка:</b> {streak}/6 д.\n"
        f"🏆 <b>Уровень:</b> {title}\n"
        f"{bar} <b>{progress}%</b>\n"
        f"⭐ XP: <b>{int(user['xp'])}</b>" + (f" / {next_xp}" if next_xp else " / MAX") + "\n"
        f"⏱ <b>След. кейс:</b> {next_case}\n"
        "🔑 <b>След. ключ:</b> пока не используется\n"
        f"🔥 <b>Активность:</b> {min(streak, 6)}/6 д.\n"
        "🌍 <b>Установленные страны номеров:</b> РФ, Украина, Беларусь, Казахстан\n\n"
        "💼 <b>АККАУНТ:</b>\n"
        f"💰 Баланс: <b>{money(user['balance'])}</b>\n"
        f"🔑 Ключей: <b>0</b>\n"
        f"🎁 Кейсов открыто: <b>{user['cases_opened']}</b>\n"
        f"📦 Номеров: <b>{plate_count}</b>\n"
        f"💀 Клан: <b>{escape(clan_name)}</b>\n\n"
        "📊 <b>СТАТИСТИКА:</b>\n"
        f"🚘 Уникальных машин: <b>{unique}/{len(CARS)}</b>\n"
        f"🚗 Всего машин: <b>{total}</b>\n"
        f"🔢 Всего номеров: <b>{plate_count}</b>\n"
        f"👥 Рефералов: <b>{user['referrals']}</b>\n\n"
        "Выбери действие ниже:"
    )
    await message.answer(text, reply_markup=extended_menu_keyboard(), parse_mode="HTML")


@dp.message(lambda m: m.text == "🗂 Коллекция")
async def collection_button(message: Message):
    await show_collection(message, message.from_user.id, 0, edit=False)


@dp.message(lambda m: m.text == "🔢 Коллекция номеров")
async def number_collection_button(message: Message):
    await show_number_collection(message, message.from_user.id, 0, edit=False)


@dp.message(lambda m: m.text == "💀 Кланы")
async def clans_button(message: Message):
    text, _ = clan_list_text()
    await message.answer(text, reply_markup=clans_keyboard(), parse_mode="HTML")


@dp.message(lambda m: m.text == "💀 Мой клан")
async def my_clan_button(message: Message):
    clan = get_user_clan(message.from_user.id)
    if not clan:
        await message.answer(
            "💀 <b>МОЙ КЛАН</b>\n\n"
            f"Ты пока не состоишь в клане.\n\n➕ Создание клана: <b>{money(CLAN_CREATE_PRICE)}</b>\n👥 Максимум: <b>{CLAN_MAX_MEMBERS}</b> участников.",
            reply_markup=my_clan_keyboard(message.from_user.id),
            parse_mode="HTML"
        )
        return
    await message.answer(clan_text(clan), reply_markup=my_clan_keyboard(message.from_user.id), parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("plates:page:"))
async def plates_page_callback(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await show_number_collection(callback.message, callback.from_user.id, page, edit=True)
    await callback.answer()


@dp.callback_query(lambda c: c.data in {
    "plates:noop", "plates:count", "plates:minus", "plates:plus",
    "plates:country", "plates:type", "plates:accounting", "plates:duplicates",
    "plates:search", "plates:filters", "plates:hide"
})
async def plates_collection_actions(callback: CallbackQuery):
    data = callback.data
    if data == "plates:country":
        await callback.answer("🌍 Фильтр страны: РФ / Украина / Беларусь / Казахстан", show_alert=True)
        return
    if data == "plates:type":
        await callback.answer("🏷 Тип: обычный гражданский номер", show_alert=True)
        return
    if data == "plates:accounting":
        await callback.answer("🔢 Учёт: в текущей версии номера хранятся без статуса учёта", show_alert=True)
        return
    if data == "plates:duplicates":
        await callback.answer("📦 Дубликатов сейчас: 0", show_alert=True)
        return
    if data == "plates:search":
        await callback.answer("🔎 Поиск номера будет добавлен следующим обновлением.", show_alert=True)
        return
    if data == "plates:filters":
        await callback.answer("📊 Фильтры: страна, тип и статус учёта.", show_alert=True)
        return
    if data == "plates:hide":
        await callback.answer("❌ Скрытие уже имеющихся номеров пока не включено.", show_alert=True)
        return
    if data == "plates:minus" or data == "plates:plus":
        await callback.answer("ℹ️ Счётчик показывает количество твоих номеров.")
        return
    await callback.answer()


@dp.callback_query(lambda c: c.data == "clan:list")
async def clan_list_callback(callback: CallbackQuery):
    text, _ = clan_list_text()
    await callback.message.edit_text(text, reply_markup=clans_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "clan:create")
async def clan_create_start(callback: CallbackQuery, state: FSMContext):
    if get_user_clan(callback.from_user.id):
        await callback.answer("❌ Ты уже состоишь в клане.", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    await state.set_state(ClanCreateState.name)
    await callback.message.answer(
        "➕ <b>СОЗДАНИЕ КЛАНА</b>\n\n"
        f"💰 Стоимость: <b>{money(CLAN_CREATE_PRICE)}</b>\n"
        f"👥 Максимум участников: <b>{CLAN_MAX_MEMBERS}</b>\n\n"
        "Напиши название клана от 3 до 24 символов.", parse_mode="HTML"
    )
    await callback.answer()


@dp.message(ClanCreateState.name)
async def clan_create_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    clan, error = create_clan(message.from_user.id, name)
    if error:
        await message.answer(error)
        return
    await state.clear()
    await message.answer(
        f"🎉 <b>КЛАН СОЗДАН!</b>\n\n💀 Название: <b>{escape(clan['name'])}</b>\n"
        f"👑 Ты владелец.\n💸 Списано: <b>{money(CLAN_CREATE_PRICE)}</b>",
        reply_markup=my_clan_keyboard(message.from_user.id), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("clan:view:"))
async def clan_view_callback(callback: CallbackQuery):
    clan_id = int(callback.data.split(":")[2])
    clan = get_clan_by_id(clan_id)
    if not clan:
        await callback.answer("❌ Клан не найден.", show_alert=True)
        return
    await callback.message.edit_text(clan_text(clan), reply_markup=clan_view_keyboard(clan_id, callback.from_user.id), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("clan:join:"))
async def clan_join_callback(callback: CallbackQuery):
    clan_id = int(callback.data.split(":")[2])
    ok, error = join_clan(callback.from_user.id, clan_id)
    if not ok:
        await callback.answer(error, show_alert=True)
        return
    clan = get_clan_by_id(clan_id)
    await callback.message.edit_text("✅ <b>Ты вступил в клан!</b>\n\n" + clan_text(clan), reply_markup=clan_view_keyboard(clan_id, callback.from_user.id), parse_mode="HTML")
    await callback.answer("Добро пожаловать в клан!")


@dp.callback_query(lambda c: c.data.startswith("clan:members:"))
async def clan_members_callback(callback: CallbackQuery):
    clan_id = int(callback.data.split(":")[2])
    clan = get_clan_by_id(clan_id)
    my_clan = get_user_clan(callback.from_user.id)
    if not clan or not my_clan or my_clan["id"] != clan_id:
        await callback.answer("❌ Ты не состоишь в этом клане.", show_alert=True)
        return
    await callback.message.edit_text(clan_members_text(clan), reply_markup=clan_members_keyboard(clan, callback.from_user.id), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("clan:kick:"))
async def clan_kick_callback(callback: CallbackQuery):
    target_id = int(callback.data.split(":")[2])
    ok, error = kick_clan_member(callback.from_user.id, target_id)
    if not ok:
        await callback.answer(error, show_alert=True)
        return
    clan = get_user_clan(callback.from_user.id)
    await callback.answer("✅ Игрок исключён.")
    await callback.message.edit_text(clan_members_text(clan), reply_markup=clan_members_keyboard(clan, callback.from_user.id), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "clan:leave")
async def clan_leave_callback(callback: CallbackQuery):
    ok, error = leave_clan(callback.from_user.id)
    if not ok:
        await callback.answer(error, show_alert=True)
        return
    await callback.message.edit_text(
        "🚪 <b>Ты вышел из клана.</b>\n\nТеперь можешь вступить в другой или создать свой.",
        reply_markup=my_clan_keyboard(callback.from_user.id), parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "clan:disband")
async def clan_disband_callback(callback: CallbackQuery):
    clan = get_user_clan(callback.from_user.id)
    if not clan or clan["role"] != "owner":
        await callback.answer("❌ Только владелец может расформировать клан.", show_alert=True)
        return
    ok, error = disband_clan(callback.from_user.id)
    if not ok:
        await callback.answer(error, show_alert=True)
        return
    await callback.message.edit_text("🗑 <b>Клан расформирован.</b>\n\nВсе участники были удалены из клана.", reply_markup=my_clan_keyboard(callback.from_user.id), parse_mode="HTML")
    await callback.answer("Клан удалён")


@dp.message(lambda m: m.text == "🔙 Назад")
async def back_to_reference_menu(message: Message):
    await message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=main_keyboard(),
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
    if not car:
        await callback.answer("🚘 Пока нет ни одной машины. Администратору нужно добавить машины через /admin.", show_alert=True)
        return
    with db() as conn:
        conn.execute("UPDATE users SET balance=balance-?, cases_opened=cases_opened+1, last_case_opened=?, xp=xp+100 WHERE user_id=?", (CASE_PRICE, now, user_id))
        conn.execute("""
            INSERT INTO garage(user_id, car_id, amount) VALUES (?, ?, 1)
            ON CONFLICT(user_id, car_id) DO UPDATE SET amount=amount+1
        """, (user_id, car["id"]))
        row = conn.execute("SELECT amount FROM garage WHERE user_id=? AND car_id=?", (user_id, car["id"])).fetchone()
    r = RARITIES[car["rarity"]]
    duplicate = f"\n📦 Теперь этой машины: <b>{row['amount']} шт.</b>" if row and row["amount"] > 1 else "\n✨ Новая машина в коллекции!"
    # Карточка выпадения в стиле, который ты показал на скриншоте.
    # XP машины пока 10 для всех авто; цвет выбирается случайно.
    car_xp = int(car.get("xp", 10))
    car_color = random.choice(["Красный", "Черный", "Белый", "Синий", "Серый", "Зеленый"])
    result_text = (
        f"🚘 <b>{escape(car['name'])} {car['year']}</b>\n\n"
        f"<b>💎 Редкость:</b> {escape(car['rarity'])}\n"
        f"<b>⚡️ Очки (XP):</b> {car_xp}\n"
        f"<b>💴 Цена:</b> {int(car['price']):,}\n"
        f"<b>🐴 Мощность:</b> {car['power']} л.с.\n"
        f"<b>🎨 Цвет:</b> {car_color}\n"
        f"<b>🏎 Тюнинг:</b> Нет\n"
        f"<b>🔢 На учете:</b> Нет\n\n"
        f"✨ {duplicate.strip()}\n"
        "🏠 Машина добавлена в коллекцию."
    ).replace(",", " ")
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
    if cid not in CONTAINERS:
        await callback.answer("Контейнер не найден.", show_alert=True)
        return
    if get_container_amount(callback.from_user.id, cid) <= 0:
        await callback.answer("У тебя нет такого контейнера.", show_alert=True)
        return
    car = choose_container_car(cid)
    if not car:
        await callback.answer("🚘 Для этого контейнера пока нет подходящих машин. Администратору нужно добавить машины нужной редкости.", show_alert=True)
        return
    if not remove_container(callback.from_user.id, cid):
        await callback.answer("Не удалось открыть контейнер. Попробуй ещё раз.", show_alert=True)
        return
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


@dp.callback_query(lambda c: c.data.startswith("collection:page:"))
async def collection_page_callback(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await show_collection(callback.message, callback.from_user.id, page, edit=True)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("collection:"))
async def collection_action_callback(callback: CallbackQuery):
    action = callback.data.split(":", 1)[1]
    messages = {
        "minus": "➖ Здесь можно будет уменьшать выбранное количество.",
        "plus": "➕ Здесь можно будет увеличивать выбранное количество.",
        "count": "📦 Счётчик показывает общее количество машин в твоём гараже.",
        "rarity": "💎 Выбери редкость — фильтр по Common, Uncommon, Rare, Epic, Legendary, Exclusive и Secret.",
        "brand": "🏷 Фильтр по брендам будет доступен после добавления брендов к машинам.",
        "accounting": "🔢 Учет: показывает количество каждой машины в коллекции.",
        "duplicates": "🟪 Дубли: здесь будут отображаться машины, которых у тебя больше одной.",
        "seasons": "🍂 Сезоны: раздел для сезонных машин и коллекций.",
        "search": "🔎 Поиск: используй поиск по названию машины.",
        "selected": "🚫 Выбрано: выбранные машины пока не отмечены.",
        "filters": "🚫 Фильтры: дополнительные фильтры коллекции пока не включены.",
        "hide": "❌ Скрытие машин в коллекциях пока не включено.",
    }
    await callback.answer(messages.get(action, "Функция пока не подключена."), show_alert=True)


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
    lines.append(f"1️⃣ Открой 3 кейса — <b>{min(user['cases_opened'],3)}/3</b> • 🎁 500 000$")
    lines.append(f"2️⃣ Получи Rare+ — <b>{'1/1' if rare_owned else '0/1'}</b> • 🎁 1 000 000$")
    lines.append(f"3️⃣ Пригласи друга — <b>{min(user['referrals'],1)}/1</b> • 🎁 750 000$")
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
        "🎁 За нового игрока: <b>250 000$</b>", parse_mode="HTML"
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
        created = start_new_auction()
        if created:
            text = "✅ <b>Новый аукцион создан!</b>\n\n" + auction_text(get_auction())
        else:
            text = "⚠️ <b>Аукцион не создан.</b>\n\nСначала добавь хотя бы одну машину редкости <b>Exclusive</b> через «➕ Добавить машину»."
        await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
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
    await message.answer("4️⃣ Введи цену машины в долларах (например: 25000000):")


@dp.message(AddCarState.price)
async def add_car_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: price=int((message.text or "").replace(" ", "").replace("$", ""))
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
            # Render/внешний мониторинг может проверять / и /health.
            # Важно: сам бот не может отменить автоматический sleep Free Web Service;
            # для пробуждения Render нужен внешний HTTP-запрос.
            if self.path in ("/", "/health", "/healthz"):
                body = b"OK - Zona CarCase Bot is alive"
                self.send_response(200)
            else:
                body = b"Not Found"
                self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, format, *args):
            pass
    server = HTTPServer(("0.0.0.0", port), Handler)
    logging.info("WEB SERVER: listening on 0.0.0.0:%s", port)
    server.serve_forever()


async def run_bot_forever():
    """
    Бесконечный цикл запуска Telegram polling.
    Если Telegram/сеть/Render временно оборвут соединение,
    бот автоматически переподключится и продолжит работу.
    """
    reconnect_delay = 5

    while True:
        bot = None
        auction_task = None
        try:
            # После любого переподключения перечитываем сохранённые данные из SQLite.
            # Это не обнуляет базу — наоборот, гарантирует, что добавленные машины
            # снова попадут в память после перезапуска polling.
            init_db()
            load_custom_cars()
            logging.info("BOT: данные восстановлены | cars=%s | db=%s", len(CARS), os.path.abspath(DB_FILE))

            bot = Bot(token=TOKEN)

            # Сбрасываем старый webhook и все накопившиеся обновления.
            await bot.delete_webhook(drop_pending_updates=True)

            # Фоновый аукцион запускаем для каждого нового процесса polling.
            auction_task = asyncio.create_task(auction_loop(bot))

            logging.info("BOT: polling запущен")
            await dp.start_polling(
                bot,
                polling_timeout=30,
                handle_as_tasks=True,
                allowed_updates=dp.resolve_used_update_types(),
            )

            # Если polling завершился без исключения — всё равно перезапускаем.
            logging.warning("BOT: polling остановился, перезапуск через %s сек.", reconnect_delay)
            reconnect_delay = 5

        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception(
                "BOT: соединение/поток polling завершился с ошибкой. "
                "Перезапуск через %s сек.",
                reconnect_delay,
            )
        finally:
            if auction_task:
                auction_task.cancel()
                try:
                    await auction_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logging.exception("BOT: ошибка остановки auction_loop")

            if bot:
                try:
                    await bot.session.close()
                except Exception:
                    pass

        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 60)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    if not TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Установи переменную окружения BOT_TOKEN.")

    init_db()
    load_custom_cars()

    logging.info(
        "Zona CarCase V3 | cars=%s | db=%s",
        len(CARS),
        os.path.abspath(DB_FILE),
    )

    # HTTP-сервер нужен Render: он слушает PORT и отвечает на health checks.
    # На бесплатном Render внешний мониторинг может периодически обращаться к /health,
    # но это не является гарантией непрерывной работы — сам Render может усыпить сервис.
    threading.Thread(target=run_web_server, daemon=True, name="render-healthcheck").start()

    if not get_auction() and CARS_BY_RARITY.get("Exclusive"):
        start_new_auction()

    # Главное: бот теперь сам переподключается при временных сбоях.
    await run_bot_forever()


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logging.info("BOT: остановка вручную.")
            break
        except Exception:
            logging.exception("BOT: критическая ошибка процесса. Перезапуск через 10 сек.")
            time.sleep(10)
