import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid
from urllib.parse import unquote

from config import (
    BOT_TOKEN, API_ID, API_HASH, SESSION_NAME,
    POLL_INTERVAL_TONNEL, POLL_INTERVAL_PORTALS, POLL_INTERVAL_MRKT,
    load_chat_id, save_chat_id, save_portals_auth,
)
from storage import SeenStore
from notifier import notify
from adapters import tonnel_adapter, portals_adapter, mrkt_adapter

seen = SeenStore()
state_data = {"chat_id": load_chat_id()}
login_done = asyncio.Event()

dp = Dispatcher(storage=MemoryStorage())

class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()

pyro = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

async def fetch_portals_auth():
    """Достаём tgWebAppData для Portals через уже залогиненный аккаунт."""
    bot_entity = await pyro.get_users("portals")
    peer = await pyro.resolve_peer("portals")
    bot = InputUser(user_id=bot_entity.id, access_hash=bot_entity.raw.access_hash)
    bot_app = InputBotAppShortName(bot_id=bot, short_name="market")
    web_view = await pyro.invoke(RequestAppWebView(peer=peer, app=bot_app, platform="android"))
    init_data = unquote(web_view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0])
    save_portals_auth(init_data)

@dp.message(CommandStart())
async def on_start(message: Message, fsm: FSMContext):
    state_data["chat_id"] = message.chat.id
    save_chat_id(message.chat.id)

    if os.path.exists(f"{SESSION_NAME}.session"):
        await message.answer("Уже привязан. Буду присылать новые лоты сюда.")
        login_done.set()
        return

    await fsm.set_state(Login.phone)
    await message.answer(
        "Первый запуск. Нужно привязать твой Telegram-аккаунт (для MRKT и Portals).\n\n"
        "Пришли номер телефона в формате +79991234567"
    )

@dp.message(Login.phone)
async def got_phone(message: Message, fsm: FSMContext):
    phone = message.text.strip()
    try:
        sent = await pyro.send_code(phone)
    except PhoneNumberInvalid:
        await message.answer("Неверный формат номера, попробуй ещё раз (+79991234567)")
        return
    await fsm.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
    await fsm.set_state(Login.code)
    await message.answer("Код отправлен в Telegram (в само приложение). Пришли его сюда.")

@dp.message(Login.code)
async def got_code(message: Message, fsm: FSMContext):
    data = await fsm.get_data()
    code = message.text.strip()
    try:
        await pyro.sign_in(data["phone"], data["phone_code_hash"], code)
    except SessionPasswordNeeded:
        await fsm.set_state(Login.password)
        await message.answer("На аккаунте включён облачный пароль (2FA). Пришли его сюда.")
        return
    except PhoneCodeInvalid:
        await message.answer("Код неверный, пришли ещё раз.")
        return
    await finish_login(message, fsm)

@dp.message(Login.password)
async def got_password(message: Message, fsm: FSMContext):
    try:
        await pyro.check_password(message.text.strip())
    except Exception as e:
        await message.answer(f"Пароль не подошёл: {e}\nПопробуй ещё раз.")
        return
    await finish_login(message, fsm)

async def finish_login(message: Message, fsm: FSMContext):
    await fsm.clear()
    try:
        await fetch_portals_auth()
    except Exception as e:
        print(f"[login] portals auth error: {e}")
    await message.answer("✅ Готово! Аккаунт привязан, начинаю парсить лоты.")
    login_done.set()

@dp.message()
async def on_any_message(message: Message, fsm: FSMContext):
    cur = await fsm.get_state()
    if cur is not None:
        return  # мы посреди логина, ждём ответ по сценарию выше
    if state_data["chat_id"] is None:
        state_data["chat_id"] = message.chat.id
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
                        if state_data["chat_id"]:
                            await notify(bot, state_data["chat_id"], listing)
        except Exception as e:
            print(f"[{source_name}] poll loop error: {e}")
        await asyncio.sleep(interval)

async def start_pollers(bot: Bot):
    await login_done.wait()  # ждём, пока привяжется аккаунт
    await asyncio.gather(
        poll_source(bot, "tonnel", tonnel_adapter.fetch_latest, POLL_INTERVAL_TONNEL),
        poll_source(bot, "portals", portals_adapter.fetch_latest, POLL_INTERVAL_PORTALS),
        poll_source(bot, "mrkt", mrkt_adapter.fetch_latest, POLL_INTERVAL_MRKT),
    )

async def main():
    bot = Bot(token=BOT_TOKEN)
    await pyro.connect()

    if os.path.exists(f"{SESSION_NAME}.session"):
        login_done.set()  # уже логинились раньше, сразу можно парсить

    print("Напиши боту /start в Telegram.")
    await asyncio.gather(
        dp.start_polling(bot),
        start_pollers(bot),
    )

if __name__ == "__main__":
    asyncio.run(main())
