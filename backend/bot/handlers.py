"""Хендлеры Telegram-бота (aiogram 3): /start + кнопки периодов.

Кнопки: Сегодня · Вчера · Неделя · Месяц · Товары · Расходы.
Вся логика — в reports.py (БД→metrics→formatting); тут только маршрутизация.

Доступ к синхронной БД из async-хендлера для SQLite-MVP делаем напрямую (запросы
короткие). При переезде на Postgres/нагрузку обернуть в asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from backend import dashboard
from backend.bot import reports
from backend.bot.config import parse_owner_ids

log = logging.getLogger(__name__)
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


def _owner_chat_ids() -> tuple[int, ...]:
    """ID владельцев из .env (те же, что у утренней рассылки). Пусто — не заданы."""
    return parse_owner_ids(os.getenv("TELEGRAM_OWNER_CHAT_ID", ""))


@router.message(Command("start"))
async def on_start(message: Message) -> None:
    await message.answer(reports.format_start_text(), reply_markup=MAIN_KEYBOARD)


@router.message(Command("dashboard"))
async def on_dashboard(message: Message) -> None:
    """Прислать ссылку на Mini App (дашборд). Только владельцам."""
    owner_ids = _owner_chat_ids()
    if not owner_ids:
        await message.answer(
            "Команда выключена: не задан TELEGRAM_OWNER_CHAT_ID — некому доверить "
            "финансовую панель."
        )
        return
    if message.chat.id not in owner_ids:
        await message.answer("Команда доступна только владельцам.")
        return

    webapp_url = os.getenv("WEBAPP_URL")
    if not webapp_url:
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if render_url:
            webapp_url = f"{render_url.rstrip('/')}/app"

    if not webapp_url:
        # Fallback to legacy HTML file approach if WEBAPP_URL is not configured
        await message.answer("Собираю панель (старый формат)…")
        try:
            html = await asyncio.to_thread(dashboard.build_html)
        except (Exception, SystemExit):
            log.exception("Не удалось собрать ops-панель")
            await message.answer("Не удалось собрать панель — смотри логи бота.")
            return

        file = BufferedInputFile(html.encode("utf-8"), filename="darwin_dashboard.html")
        await message.answer_document(file, caption="Свежая ops-панель «Дарвин» — открой файл в браузере.")
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.types.web_app_info import WebAppInfo

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Открыть Дашборд", web_app=WebAppInfo(url=webapp_url))]
    ])
    
    await message.answer("Откройте интерактивную панель управления прямо в Telegram:", reply_markup=keyboard)


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
