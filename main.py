"""Gift lot watcher: Tonnel / Portals / MRKT → Telegram alerts."""

from __future__ import annotations

import asyncio
import os
import shutil
from urllib.parse import unquote

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from pyrogram import Client
from pyrogram.errors import PhoneCodeInvalid, PhoneNumberInvalid, SessionPasswordNeeded
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.functions.users import GetUsers
from pyrogram.raw.types import InputBotAppShortName, InputUser

from adapters import mrkt, portals, tonnel
from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    FETCH_LIMIT,
    MRKT_SESSION_NAME,
    POLL_INTERVAL,
    PORTALS_AUTH_REFRESH,
    SESSION_NAME,
    load_chat_id,
    load_portals_auth,
    save_chat_id,
    save_portals_auth,
)
from notifier import notify
from storage import SeenStore


class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()


class App:
    """Everything that must live on the running event loop."""

    def __init__(self) -> None:
        self.seen = SeenStore()
        self.chat_id = load_chat_id()
        self.login_done: asyncio.Event | None = None
        self.dp = Dispatcher(storage=MemoryStorage())
        self.pyro: Client | None = None
        self.bot: Bot | None = None
        self._register_handlers()

    def ready(self) -> asyncio.Event:
        assert self.login_done is not None
        return self.login_done

    def _register_handlers(self) -> None:
        self.dp.message(CommandStart())(self.on_start)
        self.dp.message(Login.phone)(self.on_phone)
        self.dp.message(Login.code)(self.on_code)
        self.dp.message(Login.password)(self.on_password)
        self.dp.message()(self.on_any)

    def sync_mrkt_session(self) -> None:
        src, dst = f"{SESSION_NAME}.session", f"{MRKT_SESSION_NAME}.session"
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                print(f"[session] {e}")

    async def refresh_portals_auth(self) -> None:
        assert self.pyro is not None
        peer = await self.pyro.resolve_peer("portals")
        users = await self.pyro.invoke(GetUsers(id=[peer]))
        bot_raw = users[0]
        bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
        app = InputBotAppShortName(bot_id=bot, short_name="market")
        view = await self.pyro.invoke(
            RequestAppWebView(peer=peer, app=app, platform="desktop")
        )
        raw = unquote(view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0])
        save_portals_auth(f"tma {raw}")
        print("[portals] auth ok")

    async def on_start(self, message: Message, state: FSMContext) -> None:
        self.chat_id = message.chat.id
        save_chat_id(message.chat.id)

        if os.path.exists(f"{SESSION_NAME}.session"):
            await message.answer(
                "Уже привязан. Шлю новые лоты 2–60k TON "
                "(лёгкий / средний / сложный / хардкор)."
            )
            self.login_done.set()
            return

        await state.set_state(Login.phone)
        await message.answer(
            "Первый запуск — привяжи Telegram-аккаунт (MRKT + Portals).\n"
            "Пришли номер в формате +79991234567"
        )

    async def on_phone(self, message: Message, state: FSMContext) -> None:
        assert self.pyro is not None
        phone = (message.text or "").strip()
        try:
            sent = await self.pyro.send_code(phone)
        except PhoneNumberInvalid:
            await message.answer("Неверный номер. Пример: +79991234567")
            return
        await state.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
        await state.set_state(Login.code)
        await message.answer("Код ушёл в Telegram. Пришли его сюда.")

    async def on_code(self, message: Message, state: FSMContext) -> None:
        assert self.pyro is not None
        data = await state.get_data()
        code = (message.text or "").strip()
        try:
            await self.pyro.sign_in(data["phone"], data["phone_code_hash"], code)
        except SessionPasswordNeeded:
            await state.set_state(Login.password)
            await message.answer("Нужен облачный пароль (2FA). Пришли его.")
            return
        except PhoneCodeInvalid:
            await message.answer("Код неверный, попробуй ещё.")
            return
        await self._finish_login(message, state)

    async def on_password(self, message: Message, state: FSMContext) -> None:
        assert self.pyro is not None
        try:
            await self.pyro.check_password((message.text or "").strip())
        except Exception as e:
            await message.answer(f"Пароль не подошёл: {e}")
            return
        await self._finish_login(message, state)

    async def _finish_login(self, message: Message, state: FSMContext) -> None:
        await state.clear()
        self.sync_mrkt_session()
        try:
            await self.refresh_portals_auth()
        except Exception as e:
            print(f"[portals] auth error: {e}")
        await message.answer("✅ Готово. Слежу за новыми лотами 2–60k TON.")
        self.login_done.set()

    async def on_any(self, message: Message, state: FSMContext) -> None:
        if await state.get_state() is not None:
            return
        if self.chat_id is None:
            self.chat_id = message.chat.id
            save_chat_id(message.chat.id)
            await message.answer("Ок, буду слать лоты сюда.")

    async def poll(self, name: str, fetch) -> None:
        while True:
            try:
                listings = await fetch(limit=FETCH_LIMIT)
                had = self.seen.has_history(name)
                fresh = [x for x in reversed(listings) if self.seen.is_new(name, x.item_id)]
                if fresh:
                    self.seen.mark_many(name, [x.item_id for x in fresh])
                    if had and self.chat_id and self.bot:
                        for item in fresh:
                            await notify(self.bot, self.chat_id, item)
            except Exception as e:
                print(f"[{name}] {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def portals_auth_loop(self) -> None:
        await self.login_done.wait()
        while True:
            await asyncio.sleep(PORTALS_AUTH_REFRESH)
            try:
                if self.pyro and self.pyro.is_connected:
                    await self.refresh_portals_auth()
            except Exception as e:
                print(f"[portals] refresh: {e}")

    async def run_pollers(self) -> None:
        await self.login_done.wait()
        try:
            if not load_portals_auth() and self.pyro and self.pyro.is_connected:
                await self.refresh_portals_auth()
        except Exception as e:
            print(f"[portals] init auth: {e}")

        self.sync_mrkt_session()
        await asyncio.gather(
            self.poll("tonnel", tonnel.fetch_latest),
            self.poll("portals", portals.fetch_latest),
            self.poll("mrkt", mrkt.fetch_latest),
            self.portals_auth_loop(),
        )

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        # Event создаём здесь — уже на running loop
        self.login_done = asyncio.Event()
        self.pyro = Client(
            SESSION_NAME,
            api_id=API_ID,
            api_hash=API_HASH,
            loop=loop,
        )
        self.bot = Bot(token=BOT_TOKEN)

        await self.pyro.connect()

        if os.path.exists(f"{SESSION_NAME}.session"):
            try:
                me = await self.pyro.get_me()
                print(f"session ok: {me.first_name}")
                self.login_done.set()
            except Exception as e:
                print(f"session present but not ready: {e}")

        print("Напиши боту /start")
        try:
            await asyncio.gather(
                self.dp.start_polling(self.bot),
                self.run_pollers(),
            )
        finally:
            if self.pyro and self.pyro.is_connected:
                await self.pyro.disconnect()
            if self.bot:
                await self.bot.session.close()


async def _amain() -> None:
    # App создаётся уже внутри asyncio.run → один и тот же loop
    await App().run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
