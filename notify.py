from aiogram import Bot

from config import tier
from db import Lot


async def send_lot(bot: Bot, chat_id: int, lot: Lot) -> None:
    cat = tier(lot.price)
    if not cat:
        return
    text = (
        f"🆕 <b>{lot.title}</b>\n"
        f"Маркет: {lot.market}\n"
        f"Модель: {lot.model or '—'}\n"
        f"Цена: {lot.price:g} TON\n"
        f"Категория: {cat}\n"
        f'<a href="{lot.link}">Открыть</a>'
    )
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        print(f"[notify] {e}")
