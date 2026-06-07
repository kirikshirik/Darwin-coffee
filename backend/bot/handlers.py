"""Хендлеры Telegram-бота (aiogram 3): /start + кнопки периодов.

Кнопки: Сегодня · Вчера · Неделя · Месяц · Товары · Расходы.
Вся логика — в reports.py (БД→metrics→formatting); тут только маршрутизация.

Доступ к синхронной БД из async-хендлера для SQLite-MVP делаем напрямую (запросы
короткие). При переезде на Postgres/нагрузку обернуть в asyncio.to_thread.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from backend.bot import reports

router = Router()

BTN_TODAY = "Сегодня"
BTN_YESTERDAY = "Вчера"
BTN_WEEK = "Неделя"
BTN_MONTH = "Месяц"
BTN_PRODUCTS = "Товары"
BTN_EXPENSES = "Расходы"
BTN_FORECAST = "Прогноз"
BTN_INSIGHTS = "Аналитика"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_YESTERDAY)],
        [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_MONTH)],
        [KeyboardButton(text=BTN_PRODUCTS), KeyboardButton(text=BTN_EXPENSES)],
        [KeyboardButton(text=BTN_FORECAST), KeyboardButton(text=BTN_INSIGHTS)],
    ],
    resize_keyboard=True,
)


@router.message(Command("start"))
async def on_start(message: Message) -> None:
    await message.answer(reports.format_start_text(), reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_TODAY)
async def on_today(message: Message) -> None:
    await message.answer(reports.today_text())


@router.message(F.text == BTN_YESTERDAY)
async def on_yesterday(message: Message) -> None:
    await message.answer(reports.yesterday_text())


@router.message(F.text == BTN_WEEK)
async def on_week(message: Message) -> None:
    await message.answer(reports.week_text())


@router.message(F.text == BTN_MONTH)
async def on_month(message: Message) -> None:
    await message.answer(reports.month_text())


@router.message(F.text == BTN_PRODUCTS)
async def on_products(message: Message) -> None:
    await message.answer(reports.products_text())


@router.message(F.text == BTN_EXPENSES)
async def on_expenses(message: Message) -> None:
    await message.answer(reports.expenses_text())


@router.message(F.text == BTN_FORECAST)
async def on_forecast(message: Message) -> None:
    await message.answer(reports.forecast_text())


@router.message(F.text == BTN_INSIGHTS)
async def on_insights(message: Message) -> None:
    await message.answer(reports.insights_text())
