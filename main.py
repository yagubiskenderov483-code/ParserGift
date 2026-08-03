import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, POLL_INTERVAL_TONNEL, POLL_INTERVAL_PORTALS, POLL_INTERVAL_MRKT, load_chat_id, save_chat_id
from storage import SeenStore
from notifier import notify
from adapters import tonnel_adapter, portals_adapter, mrkt_adapter

seen = SeenStore()
state = {"chat_id": load_chat_id()}  # подхватываем сохранённый chat_id, если бот уже запускался

dp = Dispatcher()

@dp.message(CommandStart())
async def on_start(message: Message):
    state["chat_id"] = message.chat.id
    save_chat_id(message.chat.id)
    await message.answer(
        "Готово! Буду присылать новые лоты сюда.\n"
        "Категории: 🟢 2-5к / 🟡 5-10к / 🔴 10-20к / 💎 20-60к (TON)."
    )

@dp.message()
async def on_any_message(message: Message):
    # на случай если человек написал что-то до /start — тоже подхватываем чат
    if state["chat_id"] is None:
        state["chat_id"] = message.chat.id
        save_chat_id(message.chat.id)
        await message.answer("Готово! Буду присылать новые лоты сюда.")

async def poll_source(bot: Bot, source_name: str, fetch_fn, interval: int):
    first_run = True
    while True:
        try:
            listings = await fetch_fn(limit=20)
            if first_run:
                for listing in listings:
                    seen.mark_seen(source_name, listing.item_id)
                first_run = False
            else:
                for listing in reversed(listings):
                    if seen.is_new(source_name, listing.item_id):
                        seen.mark_seen(source_name, listing.item_id)
                        if state["chat_id"]:
                            await notify(bot, state["chat_id"], listing)
        except Exception as e:
            print(f"[{source_name}] poll loop error: {e}")
        await asyncio.sleep(interval)

async def main():
    bot = Bot(token=BOT_TOKEN)

    if state["chat_id"] is None:
        print("Чат ещё не выбран. Напиши боту /start в Telegram — он сам запомнит куда слать лоты.")

    pollers = [
        poll_source(bot, "tonnel", tonnel_adapter.fetch_latest, POLL_INTERVAL_TONNEL),
        poll_source(bot, "portals", portals_adapter.fetch_latest, POLL_INTERVAL_PORTALS),
        poll_source(bot, "mrkt", mrkt_adapter.fetch_latest, POLL_INTERVAL_MRKT),
    ]

    await asyncio.gather(dp.start_polling(bot), *pollers)

if __name__ == "__main__":
    asyncio.run(main())
