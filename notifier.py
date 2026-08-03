from aiogram import Bot
from adapters.base import Listing
from config import classify_price

async def notify(bot: Bot, chat_id: int, listing: Listing):
    tier = classify_price(listing.price)
    if tier is None:
        return  # цена вне диапазонов 2000-60000 — пропускаем

    text = (
        f"🆕 <b>{listing.name}</b>\n"
        f"Площадка: {listing.source}\n"
        f"Модель: {listing.model or '—'}\n"
        f"Цена: {listing.price:g} TON\n"
        f"Категория: {tier}"
    )
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML",
                                disable_web_page_preview=True)
    except Exception as e:
        print(f"[notifier] send error: {e}")
