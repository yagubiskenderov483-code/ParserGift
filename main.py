"""Gift lot watcher: Tonnel / Portals / MRKT → Telegram.

Build stamp must appear in container logs. If logs still show the old
startup crash at main.py:148 — the host is running a stale image/commit.
"""

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

BUILD = os.getenv("PARSERGIFT_BUILD", "2026-08-03-v3-rewrite")


class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()


def _new_pyro() -> Client:
    """Always create Client on the currently running loop."""
    return Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        loop=asyncio.get_running_loop(),
    )


class App:
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

    async def with_pyro(self, fn):
        """Short-lived pyrogram session — connect, work, disconnect."""
        client = _new_pyro()
        await client.connect()
        try:
            return await fn(client)
        finally:
            if client.is_connected:
                await client.disconnect()

    async def refresh_portals_auth(self) -> None:
        async def _do(client: Client) -> None:
            peer = await client.resolve_peer("portals")
            users = await client.invoke(GetUsers(id=[peer]))
            bot_raw = users[0]
            bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
            app = InputBotAppShortName(bot_id=bot, short_name="market")
            view = await client.invoke(
                RequestAppWebView(peer=peer, app=app, platform="desktop")
            )
            raw = unquote(
                view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0]
            )
            save_portals_auth(f"tma {raw}")
            print("[portals] auth ok")

        await self.with_pyro(_do)

    async def ensure_login_client(self) -> Client:
        """Long-lived client only while phone/code login is in progress."""
        if self.pyro is None or not self.pyro.is_connected:
            self.pyro = _new_pyro()
            await self.pyro.connect()
        return self.pyro

    async def on_start(self, message: Message, state: FSMContext) -> None:
        self.chat_id = message.chat.id
        save_chat_id(message.chat.id)

        if os.path.exists(f"{SESSION_NAME}.session"):
            await message.answer(
                f"Уже привязан (build {BUILD}).\n"
                "Шлю новые лоты 2–60k TON (лёгкий / средний / сложный / хардкор)."
            )
            self.ready().set()
            return

        await self.ensure_login_client()
        await state.set_state(Login.phone)
        await message.answer(
            "Первый запуск — привяжи Telegram-аккаунт (MRKT + Portals).\n"
            "Пришли номер в формате +79991234567"
        )

    async def on_phone(self, message: Message, state: FSMContext) -> None:
        client = await self.ensure_login_client()
        phone = (message.text or "").strip()
        try:
            sent = await client.send_code(phone)
        except PhoneNumberInvalid:
            await message.answer("Неверный номер. Пример: +79991234567")
            return
        await state.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
        await state.set_state(Login.code)
        await message.answer("Код ушёл в Telegram. Пришли его сюда.")

    async def on_code(self, message: Message, state: FSMContext) -> None:
        client = await self.ensure_login_client()
        data = await state.get_data()
        code = (message.text or "").strip()
        try:
            await client.sign_in(data["phone"], data["phone_code_hash"], code)
        except SessionPasswordNeeded:
            await state.set_state(Login.password)
            await message.answer("Нужен облачный пароль (2FA). Пришли его.")
            return
        except PhoneCodeInvalid:
            await message.answer("Код неверный, попробуй ещё.")
            return
        await self._finish_login(message, state)

    async def on_password(self, message: Message, state: FSMContext) -> None:
        client = await self.ensure_login_client()
        try:
            await client.check_password((message.text or "").strip())
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
        # login client no longer needed
        if self.pyro and self.pyro.is_connected:
            await self.pyro.disconnect()
        self.pyro = None
        await message.answer(f"✅ Готово (build {BUILD}). Слежу за лотами 2–60k TON.")
        self.ready().set()

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
                fresh = [
                    x for x in reversed(listings) if self.seen.is_new(name, x.item_id)
                ]
                if fresh:
                    self.seen.mark_many(name, [x.item_id for x in fresh])
                    if had and self.chat_id and self.bot:
                        for item in fresh:
                            await notify(self.bot, self.chat_id, item)
            except Exception as e:
                print(f"[{name}] {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def portals_auth_loop(self) -> None:
        await self.ready().wait()
        while True:
            await asyncio.sleep(PORTALS_AUTH_REFRESH)
            try:
                await self.refresh_portals_auth()
            except Exception as e:
                print(f"[portals] refresh: {e}")

    async def run_pollers(self) -> None:
        await self.ready().wait()
        try:
            if not load_portals_auth() and os.path.exists(f"{SESSION_NAME}.session"):
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
        self.login_done = asyncio.Event()
        self.bot = Bot(token=BOT_TOKEN)

        # IMPORTANT: no pyro.connect() on startup — that was the Docker crash.
        if os.path.exists(f"{SESSION_NAME}.session"):
            print(f"[{BUILD}] session file found — skip pyro startup connect")
            self.login_done.set()
        else:
            print(f"[{BUILD}] no session yet — wait for /start login")

        print(f"[{BUILD}] Напиши боту /start")
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
    print(f"=== ParserGift {BUILD} starting ===")
    await App().run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
