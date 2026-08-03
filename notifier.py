from aiogram import Bot
from adapters.base import Listing
from config import classify_price

async def notify(bot: Bot, chat_id: int, listing: Listing):
    tier = classify_price(listing.price)
    if tier is None:
        return  # вне 2000–60000 — пропускаем

    lines = [
        f"🆕 <b>{listing.name}</b>",
        f"Площадка: {listing.source}",
        f"Модель: {listing.model or '—'}",
        f"Цена: {listing.price:g} TON",
        f"Категория: {tier}",
    ]
    if listing.url:
        lines.append(f'<a href="{listing.url}">Открыть</a>')

    try:
        await bot.send_message(
            chat_id,
            "\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[notifier] send error: {e}")
