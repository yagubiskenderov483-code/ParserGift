import asyncio
import os
import shutil

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.functions.users import GetUsers
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid
from urllib.parse import unquote

from config import (
    BOT_TOKEN, API_ID, API_HASH, SESSION_NAME, MRKT_SESSION_NAME,
    POLL_INTERVAL_TONNEL, POLL_INTERVAL_PORTALS, POLL_INTERVAL_MRKT,
    PORTALS_AUTH_REFRESH_EVERY, FETCH_LIMIT,
    load_chat_id, save_chat_id, save_portals_auth, load_portals_auth,
)
from storage import SeenStore
from notifier import notify
from adapters import tonnel_adapter, portals_adapter, mrkt_adapter

seen = SeenStore()
state_data: dict = {"chat_id": load_chat_id(), "pyro": None, "login_done": None}

dp = Dispatcher(storage=MemoryStorage())

class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()

def get_pyro() -> Client:
    client = state_data["pyro"]
    if client is None:
        raise RuntimeError("Pyrogram client is not initialized yet")
    return client

def get_login_done() -> asyncio.Event:
    event = state_data["login_done"]
    if event is None:
        raise RuntimeError("login_done event is not initialized yet")
    return event

def sync_mrkt_session():
    """После логина копируем сессию для MRKT (amrkt), чтобы не входить второй раз."""
    src = f"{SESSION_NAME}.session"
    dst = f"{MRKT_SESSION_NAME}.session"
    if os.path.exists(src):
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[login] mrkt session copy: {e}")

async def fetch_portals_auth():
    """Достаём tgWebAppData для Portals через уже залогиненный аккаунт."""
    pyro = get_pyro()
    peer = await pyro.resolve_peer("portals")
    user_full = await pyro.invoke(GetUsers(id=[peer]))
    bot_raw = user_full[0]
    bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
    bot_app = InputBotAppShortName(bot_id=bot, short_name="market")
    web_view = await pyro.invoke(
        RequestAppWebView(peer=peer, app=bot_app, platform="desktop")
    )
    init_data = unquote(
        web_view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0]
    )
    save_portals_auth(f"tma {init_data}")
    print("[portals] auth refreshed")

@dp.message(CommandStart())
async def on_start(message: Message, fsm: FSMContext):
    state_data["chat_id"] = message.chat.id
    save_chat_id(message.chat.id)

    if os.path.exists(f"{SESSION_NAME}.session"):
        await message.answer(
            "Уже привязан. Буду моментально присылать новые лоты "
            "(2–60k TON: лёгкий / средний / сложный / хардкор)."
        )
        get_login_done().set()
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
        sent = await get_pyro().send_code(phone)
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
        await get_pyro().sign_in(data["phone"], data["phone_code_hash"], code)
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
        await get_pyro().check_password(message.text.strip())
    except Exception as e:
        await message.answer(f"Пароль не подошёл: {e}\nПопробуй ещё раз.")
        return
    await finish_login(message, fsm)

async def finish_login(message: Message, fsm: FSMContext):
    await fsm.clear()
    sync_mrkt_session()
    try:
        await fetch_portals_auth()
    except Exception as e:
        print(f"[login] portals auth error: {e}")
    await message.answer(
        "✅ Готово! Аккаунт привязан.\n"
        "Слежу за Tonnel / Portals / MRKT и сразу шлю новые лоты 2–60k TON."
    )
    get_login_done().set()

@dp.message()
async def on_any_message(message: Message, fsm: FSMContext):
    cur = await fsm.get_state()
    if cur is not None:
        return  # посреди логина
    if state_data["chat_id"] is None:
        state_data["chat_id"] = message.chat.id
        save_chat_id(message.chat.id)
        await message.answer("Готово! Буду присылать новые лоты сюда.")

async def poll_source(bot: Bot, source_name: str, fetch_fn, interval: int):
    """Поллинг ~каждую секунду. Первый проход (или пустой seen) только засеивает id,
    дальше — моментальные пуши по новым лотам."""
    while True:
        try:
            listings = await fetch_fn(limit=FETCH_LIMIT)
            had_history = seen.has_history(source_name)
            fresh: list = []
            for listing in reversed(listings):
                if seen.is_new(source_name, listing.item_id):
                    fresh.append(listing)
            if fresh:
                seen.mark_seen_many(source_name, [x.item_id for x in fresh])
                if had_history and state_data["chat_id"]:
                    for listing in fresh:
                        await notify(bot, state_data["chat_id"], listing)
        except Exception as e:
            print(f"[{source_name}] poll loop error: {e}")
        await asyncio.sleep(interval)

async def refresh_portals_auth_loop():
    await get_login_done().wait()
    while True:
        await asyncio.sleep(PORTALS_AUTH_REFRESH_EVERY)
        try:
            pyro = get_pyro()
            if pyro.is_connected:
                await fetch_portals_auth()
        except Exception as e:
            print(f"[portals] auth refresh error: {e}")

async def start_pollers(bot: Bot):
    await get_login_done().wait()
    try:
        if not load_portals_auth() and get_pyro().is_connected:
            await fetch_portals_auth()
    except Exception as e:
        print(f"[portals] initial auth: {e}")

    sync_mrkt_session()
    await asyncio.gather(
        poll_source(bot, "tonnel", tonnel_adapter.fetch_latest, POLL_INTERVAL_TONNEL),
        poll_source(bot, "portals", portals_adapter.fetch_latest, POLL_INTERVAL_PORTALS),
        poll_source(bot, "mrkt", mrkt_adapter.fetch_latest, POLL_INTERVAL_MRKT),
        refresh_portals_auth_loop(),
    )

async def main():
    # Client/Event только внутри running loop + явный loop=
    # иначе Pyrogram: "Future attached to a different loop"
    loop = asyncio.get_running_loop()
    state_data["login_done"] = asyncio.Event()
    pyro = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        loop=loop,
    )
    state_data["pyro"] = pyro

    bot = Bot(token=BOT_TOKEN)
    await pyro.connect()

    if os.path.exists(f"{SESSION_NAME}.session"):
        try:
            me = await pyro.get_me()
            print(f"Session OK: {me.first_name} (@{me.username})")
            get_login_done().set()
        except Exception as e:
            print(f"Session exists but not authorized yet: {e}")

    print("Напиши боту /start в Telegram.")
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            start_pollers(bot),
        )
    finally:
        if pyro.is_connected:
            await pyro.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
