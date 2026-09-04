import asyncio
import logging
import random
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN = os.getenv("BOT_TOKEN")


dp = Dispatcher()


# =========================
# АВТОМОБИЛИ
# =========================

CARS = [
    {
        "name": "Volkswagen up!",
        "rarity": "⚪ Common",
        "price": 1200000,
        "power": 90,
        "chance": 60,
    },
    {
        "name": "BMW 320i",
        "rarity": "🟢 Uncommon",
        "price": 3500000,
        "power": 184,
        "chance": 25,
    },
    {
        "name": "BMW M5",
        "rarity": "🔵 Rare",
        "price": 12500000,
        "power": 625,
        "chance": 10,
    },
    {
        "name": "Lamborghini Huracan",
        "rarity": "🟣 Epic",
        "price": 25000000,
        "power": 640,
        "chance": 4,
    },
    {
        "name": "Bugatti Chiron",
        "rarity": "🟡 Legendary",
        "price": 85000000,
        "power": 1500,
        "chance": 1,
    },
]


CASE_PRICE = 1200000


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_keyboard():
    keyboard = ReplyKeyboardBuilder()

    keyboard.button(text="🚘 Открыть авто")
    keyboard.button(text="🏠 Гараж")
    keyboard.button(text="📝 Квесты")
    keyboard.button(text="🏆 Сезон")
    keyboard.button(text="🎁 Промокод")
    keyboard.button(text="👥 Реферальная ссылка")

    keyboard.adjust(2, 2, 2)

    return keyboard.as_markup(resize_keyboard=True)


# =========================
# КНОПКА КЕЙСА
# =========================

def case_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🎁 ОТКРЫТЬ КЕЙС",
        callback_data="open_case"
    )

    keyboard.button(
        text="⬅️ Назад",
        callback_data="back_menu"
    )

    keyboard.adjust(1)

    return keyboard.as_markup()


# =========================
# ВЫБОР АВТО
# =========================

def get_random_car():
    total = sum(car["chance"] for car in CARS)

    number = random.uniform(0, total)

    current = 0

    for car in CARS:
        current += car["chance"]

        if number <= current:
            return car

    return CARS[0]


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "🚘 <b>Добро пожаловать в Zona Car Case!</b>\n\n"
        "🎁 Открывай кейсы\n"
        "🚗 Собирай автомобили\n"
        "💰 Увеличивай свою коллекцию\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_keyboard()
    )


# =========================
# ОТКРЫТЬ АВТО
# =========================

@dp.message(lambda message: message.text == "🚘 Открыть авто")
async def open_auto(message: Message):

    await message.answer(
        "🚘 <b>АВТОМОБИЛИ</b>\n\n"
        "🎁 <b>Common Case</b>\n\n"
        "⚪ Common — 60%\n"
        "🟢 Uncommon — 25%\n"
        "🔵 Rare — 10%\n"
        "🟣 Epic — 4%\n"
        "🟡 Legendary — 1%\n\n"
        f"💰 Цена открытия: <b>{CASE_PRICE:,}₽</b>\n\n"
        "Нажми кнопку ниже 👇",
        reply_markup=case_keyboard()
    )


# =========================
# ОТКРЫТИЕ КЕЙСА
# =========================

@dp.callback_query(lambda callback: callback.data == "open_case")
async def open_case(callback: CallbackQuery):
    car = get_random_car()

    await callback.message.answer(
        "🎉 <b>КЕЙС ОТКРЫТ!</b>\\n\\n"
        f"🚘 <b>{car['name']}</b>\\n"
        f"🎯 Редкость: {car['rarity']}\\n"
        f"💰 Стоимость: {car['price']:,}₽\\n"
        f"⚡ Мощность: {car['power']} л.с.\\n\\n"
        "🔥 Поздравляем с выпадением!",
        parse_mode="HTML"
    )

    await callback.answer("🎉 Тебе выпал автомобиль!")

# =========================
# ГАРАЖ
# =========================

@dp.message(lambda message: message.text == "🏠 Гараж")
async def garage(message: Message):

    await message.answer(
        "🏠 <b>ТВОЙ ГАРАЖ</b>\n\n"
        "🚗 Пока автомобилей нет.\n\n"
        "Открой кейс через кнопку:\n"
        "🚘 Открыть авто"
    )


# =========================
# КВЕСТЫ
# =========================

@dp.message(lambda message: message.text == "📝 Квесты")
async def quests(message: Message):

    await message.answer(
        "📝 <b>КВЕСТЫ</b>\n\n"
        "1️⃣ Открой 3 кейса\n"
        "Прогресс: 0/3\n"
        "🎁 Награда: 500 000₽\n\n"
        "2️⃣ Получи Rare автомобиль\n"
        "Прогресс: ❌\n"
        "🎁 Награда: 1 000 000₽\n\n"
        "3️⃣ Пригласи друга\n"
        "Прогресс: 0/1\n"
        "🎁 Награда: 750 000₽"
    )


# =========================
# СЕЗОН
# =========================

@dp.message(lambda message: message.text == "🏆 Сезон")
async def season(message: Message):

    await message.answer(
        "🏆 <b>СЕЗОН</b>\n\n"
        "⭐ Уровень: 1\n"
        "✨ Опыт: 0 / 1000\n\n"
        "🎁 Следующая награда:\n"
        "💰 500 000₽"
    )


# =========================
# ПРОМОКОД
# =========================

@dp.message(lambda message: message.text == "🎁 Промокод")
async def promo(message: Message):

    await message.answer(
        "🎁 <b>ПРОМОКОД</b>\n\n"
        "Отправь мне промокод следующим сообщением."
    )


# =========================
# РЕФЕРАЛЬНАЯ ССЫЛКА
# =========================

@dp.message(lambda message: message.text == "👥 Реферальная ссылка")
async def referral(message: Message):

    user_id = message.from_user.id

    await message.answer(
        "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>https://t.me/ZonaCarCaseBot?start={user_id}</code>\n\n"
        "👤 Приглашено: 0\n"
        "💰 Заработано: 0₽"
    )


# =========================
# НАЗАД
# =========================

@dp.callback_query(lambda callback: callback.data == "back_menu")
async def back_menu(callback: CallbackQuery):

    await callback.message.delete()

    await callback.message.answer(
        "🏠 Главное меню:",
        reply_markup=main_keyboard()
    )

    await callback.answer()


# =========================
# ЗАПУСК WEBHOOK
# =========================

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://zona-carcase.onrender.com/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", "10000"))

bot = Bot(token=TOKEN)


async def on_startup(bot: Bot):
    await bot.set_webhook(
        WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET
    )


async def main():
    dp.startup.register(on_startup)

    app = web.Application()

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH
    )

    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    logging.info(f"Webhook server started on port {PORT}")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
    )

if __name__ == "__main__":
    asyncio.run(main())
