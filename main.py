"""
ParserGift — моментальный парсер новых лотов
Tonnel / Portals / MRKT · 2k–60k TON

Запуск: python main.py
После старта напиши боту /start
"""

from __future__ import annotations

import asyncio
import json
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

import parse_mrkt
import parse_portals
import parse_tonnel
from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    BUILD,
    MRKT_SESSION,
    POLL_SEC,
    SESSION,
    price_tier,
)

SEEN_FILE = "seen.json"
CHAT_FILE = "chat_id.json"


# ---------- storage ----------

class SeenStore:
    def __init__(self) -> None:
        self.data: dict[str, list[str]] = {}
        self.idx: dict[str, set[str]] = {}
        if os.path.exists(SEEN_FILE):
            try:
                with open(SEEN_FILE, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        for k, v in self.data.items():
            self.idx[k] = set(v)

    def has(self, market: str) -> bool:
        return bool(self.data.get(market))

    def is_new(self, market: str, lot_id: str) -> bool:
        return lot_id not in self.idx.setdefault(market, set())

    def remember(self, market: str, ids: list[str]) -> None:
        arr = self.data.setdefault(market, [])
        s = self.idx.setdefault(market, set())
        changed = False
        for i in ids:
            if i in s:
                continue
            arr.append(i)
            s.add(i)
            changed = True
        if len(arr) > 5000:
            drop = arr[:-5000]
            self.data[market] = arr[-5000:]
            for d in drop:
                s.discard(d)
            changed = True
        if changed:
            with open(SEEN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f)


def load_chat() -> int | None:
    if not os.path.exists(CHAT_FILE):
        return None
    try:
        with open(CHAT_FILE, encoding="utf-8") as f:
            return json.load(f).get("chat_id")
    except Exception:
        return None


def save_chat(chat_id: int) -> None:
    with open(CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump({"chat_id": chat_id}, f)


# ---------- bot FSM ----------

class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()


class BotApp:
    def __init__(self) -> None:
        self.seen = SeenStore()
        self.chat_id = load_chat()
        self.ready: asyncio.Event | None = None
        self.bot: Bot | None = None
        self.user: Client | None = None
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp.message.register(self.on_start, CommandStart())
        self.dp.message.register(self.on_phone, Login.phone)
        self.dp.message.register(self.on_code, Login.code)
        self.dp.message.register(self.on_password, Login.password)
        self.dp.message.register(self.on_text, F.text)

    def go(self) -> asyncio.Event:
        assert self.ready is not None
        return self.ready

    def new_user_client(self) -> Client:
        return Client(
            SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            loop=asyncio.get_running_loop(),
        )

    async def user_connect(self) -> Client:
        if self.user is None or not self.user.is_connected:
            self.user = self.new_user_client()
            await self.user.connect()
        return self.user

    async def user_disconnect(self) -> None:
        if self.user and self.user.is_connected:
            await self.user.disconnect()
        self.user = None

    def copy_session_for_mrkt(self) -> None:
        src, dst = f"{SESSION}.session", f"{MRKT_SESSION}.session"
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                print(f"[session] {e}")

    async def refresh_portals_token(self) -> None:
        c = self.new_user_client()
        await c.connect()
        try:
            peer = await c.resolve_peer("portals")
            users = await c.invoke(GetUsers(id=[peer]))
            raw = users[0]
            bot = InputUser(user_id=raw.id, access_hash=raw.access_hash)
            app = InputBotAppShortName(bot_id=bot, short_name="market")
            view = await c.invoke(
                RequestAppWebView(peer=peer, app=app, platform="desktop")
            )
            data = unquote(
                view.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0]
            )
            parse_portals.save_auth(f"tma {data}")
            print("[portals] auth ok")
        finally:
            if c.is_connected:
                await c.disconnect()

    async def notify(self, lot: dict) -> None:
        if not self.bot or not self.chat_id:
            return
        cat = price_tier(lot["price"])
        if not cat:
            return
        text = (
            f"🆕 <b>{lot['title']}</b>\n"
            f"Маркет: {lot['market']}\n"
            f"Модель: {lot.get('model') or '—'}\n"
            f"Цена: {lot['price']:g} TON\n"
            f"Категория: {cat}\n"
            f"<a href=\"{lot['url']}\">Открыть</a>"
        )
        try:
            await self.bot.send_message(
                self.chat_id, text, parse_mode="HTML", disable_web_page_preview=True
            )
        except Exception as e:
            print(f"[notify] {e}")

    # ---- handlers ----

    async def on_start(self, message: Message, state: FSMContext) -> None:
        self.chat_id = message.chat.id
        save_chat(message.chat.id)

        if os.path.exists(f"{SESSION}.session"):
            await message.answer(
                f"Сессия есть ({BUILD}).\n"
                "Парсю новые лоты 2–60k: лёгкий / средний / сложный / хардкор."
            )
            self.go().set()
            return

        await self.user_connect()
        await state.set_state(Login.phone)
        await message.answer("Номер телефона в формате +79991234567:")

    async def on_phone(self, message: Message, state: FSMContext) -> None:
        c = await self.user_connect()
        phone = (message.text or "").strip()
        try:
            sent = await c.send_code(phone)
        except PhoneNumberInvalid:
            await message.answer("Неверный номер. Пример: +79991234567")
            return
        await state.update_data(phone=phone, phone_hash=sent.phone_code_hash)
        await state.set_state(Login.code)
        await message.answer("Код из Telegram — пришли сюда.")

    async def on_code(self, message: Message, state: FSMContext) -> None:
        c = await self.user_connect()
        data = await state.get_data()
        code = (message.text or "").strip()
        try:
            await c.sign_in(data["phone"], data["phone_hash"], code)
        except SessionPasswordNeeded:
            await state.set_state(Login.password)
            await message.answer("Облачный пароль (2FA):")
            return
        except PhoneCodeInvalid:
            await message.answer("Код неверный.")
            return
        await self.finish_login(message, state)

    async def on_password(self, message: Message, state: FSMContext) -> None:
        c = await self.user_connect()
        try:
            await c.check_password((message.text or "").strip())
        except Exception as e:
            await message.answer(f"Пароль не подошёл: {e}")
            return
        await self.finish_login(message, state)

    async def finish_login(self, message: Message, state: FSMContext) -> None:
        await state.clear()
        self.copy_session_for_mrkt()
        try:
            await self.refresh_portals_token()
        except Exception as e:
            print(f"[portals] {e}")
        await self.user_disconnect()
        await message.answer(f"✅ Готово ({BUILD}). Парсю лоты.")
        self.go().set()

    async def on_text(self, message: Message, state: FSMContext) -> None:
        if await state.get_state():
            return
        if self.chat_id is None:
            self.chat_id = message.chat.id
            save_chat(message.chat.id)
            await message.answer("Чат сохранён, жду лоты.")

    # ---- polling ----

    async def poll_market(self, name: str, fetcher) -> None:
        while True:
            try:
                lots = await fetcher()
                already = self.seen.has(name)
                fresh = [x for x in reversed(lots) if self.seen.is_new(name, x["id"])]
                if fresh:
                    self.seen.remember(name, [x["id"] for x in fresh])
                    if already:
                        for lot in fresh:
                            await self.notify(lot)
            except Exception as e:
                print(f"[{name}] {e}")
            await asyncio.sleep(POLL_SEC)

    async def portals_reauth_loop(self) -> None:
        await self.go().wait()
        while True:
            await asyncio.sleep(6 * 60 * 60)
            try:
                if os.path.exists(f"{SESSION}.session"):
                    await self.refresh_portals_token()
            except Exception as e:
                print(f"[portals] reauth: {e}")

    async def run_parsers(self) -> None:
        await self.go().wait()
        if not parse_portals.load_auth() and os.path.exists(f"{SESSION}.session"):
            try:
                await self.refresh_portals_token()
            except Exception as e:
                print(f"[portals] init: {e}")
        self.copy_session_for_mrkt()
        await asyncio.gather(
            self.poll_market("tonnel", parse_tonnel.fetch_new),
            self.poll_market("portals", parse_portals.fetch_new),
            self.poll_market("mrkt", parse_mrkt.fetch_new),
            self.portals_reauth_loop(),
        )

    async def run(self) -> None:
        print(f"=== ParserGift {BUILD} ===")
        self.ready = asyncio.Event()
        self.bot = Bot(token=BOT_TOKEN)

        if os.path.exists(f"{SESSION}.session"):
            print(f"[{BUILD}] session found")
            self.ready.set()
        else:
            print(f"[{BUILD}] send /start to bot for login")

        try:
            await asyncio.gather(
                self.dp.start_polling(self.bot),
                self.run_parsers(),
            )
        finally:
            await self.user_disconnect()
            await self.bot.session.close()


async def _amain() -> None:
    await BotApp().run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
