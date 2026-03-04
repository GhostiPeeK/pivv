import logging
import sqlite3
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ========== ТОКЕН ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_ID = 2091630272

# ========== БД ==========
conn = sqlite3.connect("pivchik.db")
cursor = conn.cursor()

# Создаем таблицы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_date TEXT
    )
''')
conn.commit()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== ПРОСТАЯ КЛАВИАТУРА ==========
def get_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔞 ПИВЧИК")
    builder.button(text="📝 Анкета")
    builder.button(text="👀 Смотреть")
    builder.button(text="❤️ Лайки")
    builder.button(text="💎 Премиум")
    builder.button(text="❓ Помощь")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Сохраняем юзера
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, message.from_user.username, message.from_user.first_name, datetime.now().isoformat()))
    conn.commit()
    
    await message.answer(
        f"🍺 Добро пожаловать в ПИВЧИК!\n\n"
        f"Тут люди находят друг друга\n\n"
        f"Нажимай кнопки ниже 👇",
        reply_markup=get_keyboard()
    )

# ========== ОБРАБОТКА КНОПОК ==========
@dp.message(lambda message: message.text == "🔞 ПИВЧИК")
async def pivchik_button(message: Message):
    await message.answer("🍺 ПИВЧИК ждет тебя!", reply_markup=get_keyboard())

@dp.message(lambda message: message.text == "📝 Анкета")
async def anketa_button(message: Message):
    await message.answer(
        "📝 Создание анкеты:\n\n"
        "Напиши /create чтобы создать анкету",
        reply_markup=get_keyboard()
    )

@dp.message(lambda message: message.text == "👀 Смотреть")
async def smotret_button(message: Message):
    await message.answer(
        "👀 Смотрим анкеты...\n\n"
        "Пока тут пусто, но скоро появятся люди!",
        reply_markup=get_keyboard()
    )

@dp.message(lambda message: message.text == "❤️ Лайки")
async def likes_button(message: Message):
    await message.answer(
        "❤️ Твои лайки:\n"
        "• Поставлено: 0\n"
        "• Получено: 0\n"
        "• Взаимных: 0",
        reply_markup=get_keyboard()
    )

@dp.message(lambda message: message.text == "💎 Премиум")
async def premium_button(message: Message):
    await message.answer(
        "💎 Премиум ПИВЧИК:\n\n"
        "• 1000 просмотров в день\n"
        "• 1000 лайков в день\n"
        "• Значок в профиле\n\n"
        "Цена: 50 ⭐ = 1 день",
        reply_markup=get_keyboard()
    )

@dp.message(lambda message: message.text == "❓ Помощь")
async def help_button(message: Message):
    await message.answer(
        "❓ Помощь:\n\n"
        "📝 Анкета - создать/редактировать\n"
        "👀 Смотреть - смотреть анкеты\n"
        "❤️ Лайки - твоя статистика\n"
        "💎 Премиум - купить премиум\n\n"
        "По вопросам: @admin",
        reply_markup=get_keyboard()
    )

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def cmd_create(message: Message):
    await message.answer(
        "📝 Создание анкеты:\n\n"
        "Отправь свое фото"
    )

@dp.message(lambda message: message.photo)
async def handle_photo(message: Message):
    await message.answer(
        "✅ Фото получено!\n\n"
        "Теперь напиши свое имя"
    )

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    
    await message.answer(
        f"👑 Админ панель\n\n"
        f"Пользователей: {users}"
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🍺 ПИВЧИК запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
