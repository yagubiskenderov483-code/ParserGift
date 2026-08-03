"""Fresh gift-lot parser. Build: scratch-2026-08-03

Watches Tonnel / Portals / MRKT for NEW listings in 2k–60k TON.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from urllib.parse import unquote

from aiogram import Bot, Dispatcher, F
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

from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    BUILD,
    MRKT_SESSION,
    POLL_SEC,
    SESSION,
)
from db import Seen, load_json, save_json
from markets import mrkt, portals, tonnel
from notify import send_lot

AUTH_PATH = "portals_auth.json"
CHAT_PATH = "chat_id.json"


class Auth(StatesGroup):
    phone = State()
    code = State()
    password = State()


class Runtime:
    def __init__(self) -> None:
        self.seen = Seen()
        self.chat_id = load_json(CHAT_PATH, "chat_id")
        self.ready: asyncio.Event | None = None
        self.bot: Bot | None = None
        self.user: Client | None = None
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp.message.register(self.cmd_start, CommandStart())
        self.dp.message.register(self.got_phone, Auth.phone)
        self.dp.message.register(self.got_code, Auth.code)
        self.dp.message.register(self.got_password, Auth.password)
        self.dp.message.register(self.any_msg, F.text)

    def event(self) -> asyncio.Event:
        assert self.ready is not None
        return self.ready

    def make_user(self) -> Client:
        return Client(
            SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            loop=asyncio.get_running_loop(),
        )

    async def open_user(self) -> Client:
        if self.user is None or not self.user.is_connected:
            self.user = self.make_user()
            await self.user.connect()
        return self.user

    async def close_user(self) -> None:
        if self.user and self.user.is_connected:
            await self.user.disconnect()
        self.user = None

    def mirror_mrkt_session(self) -> None:
        src, dst = f"{SESSION}.session", f"{MRKT_SESSION}.session"
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                print(f"[session] {e}")

    async def grab_portals_auth(self) -> None:
        async def work(c: Client) -> None:
            peer = await c.resolve_peer("portals")
            users = await c.invoke(GetUsers(id=[peer]))
            raw_bot = users[0]
            bot = InputUser(user_id=raw_bot.id, access_hash=raw_bot.access_hash)
            mini = InputBotAppShortName(bot_id=bot, short_name="market")
            view = await c.invoke(
                RequestAppWebView(peer=peer, app=mini, platform="desktop")
            )
            data = unquote(
                view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0]
            )
            save_json(AUTH_PATH, "authData", f"tma {data}")
            print("[portals] auth saved")

        # short-lived connection — never keep global pyro on boot
        c = self.make_user()
        await c.connect()
        try:
            await work(c)
        finally:
            if c.is_connected:
                await c.disconnect()

    async def cmd_start(self, message: Message, state: FSMContext) -> None:
        self.chat_id = message.chat.id
        save_json(CHAT_PATH, "chat_id", message.chat.id)

        if os.path.exists(f"{SESSION}.session"):
            await message.answer(
                f"Ок, сессия есть ({BUILD}).\n"
                "Парсю новые лоты 2–60k: лёгкий / средний / сложный / хардкор."
            )
            self.event().set()
            return

        await self.open_user()
        await state.set_state(Auth.phone)
        await message.answer("Пришли номер телефона: +79991234567")

    async def got_phone(self, message: Message, state: FSMContext) -> None:
        c = await self.open_user()
        phone = (message.text or "").strip()
        try:
            sent = await c.send_code(phone)
        except PhoneNumberInvalid:
            await message.answer("Кривой номер. Формат: +79991234567")
            return
        await state.update_data(phone=phone, hash=sent.phone_code_hash)
        await state.set_state(Auth.code)
        await message.answer("Код из Telegram — сюда.")

    async def got_code(self, message: Message, state: FSMContext) -> None:
        c = await self.open_user()
        data = await state.get_data()
        code = (message.text or "").strip()
        try:
            await c.sign_in(data["phone"], data["hash"], code)
        except SessionPasswordNeeded:
            await state.set_state(Auth.password)
            await message.answer("2FA пароль:")
            return
        except PhoneCodeInvalid:
            await message.answer("Код неверный.")
            return
        await self.finish_auth(message, state)

    async def got_password(self, message: Message, state: FSMContext) -> None:
        c = await self.open_user()
        try:
            await c.check_password((message.text or "").strip())
        except Exception as e:
            await message.answer(f"Не подошёл: {e}")
            return
        await self.finish_auth(message, state)

    async def finish_auth(self, message: Message, state: FSMContext) -> None:
        await state.clear()
        self.mirror_mrkt_session()
        try:
            await self.grab_portals_auth()
        except Exception as e:
            print(f"[portals] {e}")
        await self.close_user()
        await message.answer(f"✅ Авторизация ок ({BUILD}). Начинаю парсить.")
        self.event().set()

    async def any_msg(self, message: Message, state: FSMContext) -> None:
        if await state.get_state():
            return
        if self.chat_id is None:
            self.chat_id = message.chat.id
            save_json(CHAT_PATH, "chat_id", message.chat.id)
            await message.answer("Чат сохранён.")

    async def watch(self, name: str, fetcher) -> None:
        while True:
            try:
                lots = await fetcher()
                seeded = self.seen.known(name)
                fresh = [x for x in reversed(lots) if self.seen.is_new(name, x.lot_id)]
                if fresh:
                    self.seen.add(name, [x.lot_id for x in fresh])
                    if seeded and self.chat_id and self.bot:
                        for lot in fresh:
                            await send_lot(self.bot, self.chat_id, lot)
            except Exception as e:
                print(f"[{name}] loop: {e}")
            await asyncio.sleep(POLL_SEC)

    async def auth_refresh(self) -> None:
        await self.event().wait()
        while True:
            await asyncio.sleep(6 * 60 * 60)
            try:
                if os.path.exists(f"{SESSION}.session"):
                    await self.grab_portals_auth()
            except Exception as e:
                print(f"[portals] refresh: {e}")

    async def parsers(self) -> None:
        await self.event().wait()
        if not load_json(AUTH_PATH, "authData") and os.path.exists(f"{SESSION}.session"):
            try:
                await self.grab_portals_auth()
            except Exception as e:
                print(f"[portals] first auth: {e}")
        self.mirror_mrkt_session()
        await asyncio.gather(
            self.watch("tonnel", tonnel.latest),
            self.watch("portals", portals.latest),
            self.watch("mrkt", mrkt.latest),
            self.auth_refresh(),
        )

    async def start(self) -> None:
        print(f"=== ParserGift {BUILD} ===")
        self.ready = asyncio.Event()
        self.bot = Bot(token=BOT_TOKEN)

        if os.path.exists(f"{SESSION}.session"):
            print(f"[{BUILD}] session on disk — parsers will start after /start or immediately")
            self.ready.set()
        else:
            print(f"[{BUILD}] no session — send /start to the bot")

        try:
            await asyncio.gather(self.dp.start_polling(self.bot), self.parsers())
        finally:
            await self.close_user()
            await self.bot.session.close()


async def _run() -> None:
    await Runtime().start()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
