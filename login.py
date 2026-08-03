"""
Одноразовый скрипт для привязки твоего Telegram-аккаунта к MRKT.
Логин происходит прямо в переписке с ботом — номер и код вводишь в Telegram, не в консоли.

Запуск: python login.py
После успешного входа появится файл mrkt_session.session — он и есть привязка.
Дальше main.py будет использовать его сам, login.py больше не нужен.
"""
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid

from config import BOT_TOKEN, API_ID, API_HASH

dp = Dispatcher(storage=MemoryStorage())
pyro = Client("mrkt_session", api_id=API_ID, api_hash=API_HASH)

class Login(StatesGroup):
    phone = State()
    code = State()
    password = State()

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Login.phone)
    await message.answer(
        "Привязка MRKT-аккаунта.\n\n"
        "Пришли номер телефона в формате +79991234567"
    )

@dp.message(Login.phone)
async def got_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    try:
        sent = await pyro.send_code(phone)
    except PhoneNumberInvalid:
        await message.answer("Неверный формат номера, попробуй ещё раз (+79991234567)")
        return
    await state.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
    await state.set_state(Login.code)
    await message.answer("Код отправлен в Telegram (в само приложение, не сюда). Пришли его сюда.")

@dp.message(Login.code)
async def got_code(message: Message, state: FSMContext):
    data = await state.get_data()
    code = message.text.strip()
    try:
        await pyro.sign_in(data["phone"], data["phone_code_hash"], code)
    except SessionPasswordNeeded:
        await state.set_state(Login.password)
        await message.answer("На аккаунте включён облачный пароль (2FA). Пришли его сюда.")
        return
    except PhoneCodeInvalid:
        await message.answer("Код неверный, пришли ещё раз.")
        return
    await finish(message, state)

@dp.message(Login.password)
async def got_password(message: Message, state: FSMContext):
    try:
        await pyro.check_password(message.text.strip())
    except Exception as e:
        await message.answer(f"Пароль не подошёл: {e}\nПопробуй ещё раз.")
        return
    await finish(message, state)

async def finish(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Готово! Аккаунт привязан, файл mrkt_session.session создан.\n"
                          "Теперь можно запускать main.py — можешь остановить login.py (Ctrl+C).")

async def main():
    await pyro.connect()
    print("Открой бота в Telegram и нажми /start")
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
