import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import asyncio

# ========== ТОКЕН ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"

# ========== БД ==========
conn = sqlite3.connect("pivchik.db")
cursor = conn.cursor()

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

# ========== КЛАВИАТУРА ==========
def get_keyboard():
    """Обычная клавиатура"""
    button1 = KeyboardButton(text="Моя анкета")
    button2 = KeyboardButton(text="Смотреть")
    button3 = KeyboardButton(text="Премиум")
    button4 = KeyboardButton(text="Статистика")
    button5 = KeyboardButton(text="Помощь")
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [button1, button2],
            [button3, button4],
            [button5]
        ],
        resize_keyboard=True
    )
    return keyboard

# ========== КОМАНДА СТАРТ ==========
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    
    # Сохраняем пользователя
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, message.from_user.username, message.from_user.first_name, datetime.now().isoformat()))
    conn.commit()
    
    # Отправляем приветствие
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в ПИВЧИК!\n\n"
        f"Нажимай кнопки ниже:",
        reply_markup=get_keyboard()
    )

# ========== ОБРАБОТКА КНОПОК ==========
@dp.message(lambda message: message.text == "Моя анкета")
async def my_profile(message: Message):
    await message.answer("👤 Твоя анкета\n\nПока пусто. Создай анкету через команду /create")

@dp.message(lambda message: message.text == "Смотреть")
async def view(message: Message):
    await message.answer("👀 Смотрим анкеты...\n\nПока никого нет, но скоро появятся!")

@dp.message(lambda message: message.text == "Премиум")
async def premium(message: Message):
    await message.answer("💎 Премиум\n\n• 1500 просмотров\n• 1500 лайков\n\nЦена: 50 ⭐")

@dp.message(lambda message: message.text == "Статистика")
async def stats(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT COUNT(*) FROM views WHERE user_id = ?', (user_id,))
    views = cursor.fetchone()[0]
    await message.answer(f"📊 Статистика\n\nПросмотрено анкет: {views}")

@dp.message(lambda message: message.text == "Помощь")
async def help_msg(message: Message):
    await message.answer(
        "❓ Помощь\n\n"
        "• Моя анкета - просмотр анкеты\n"
        "• Смотреть - просмотр анкет\n"
        "• Премиум - купить премиум\n"
        "• Статистика - твоя статистика\n\n"
        "По вопросам: @admin"
    )

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def create_profile(message: Message):
    await message.answer(
        "📝 Создание анкеты\n\n"
        "Отправь фото:",
        reply_markup=get_keyboard()
    )

@dp.message(lambda message: message.photo)
async def get_photo(message: Message):
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id
    
    # Сохраняем в БД (упрощенно)
    cursor.execute('''
        INSERT OR REPLACE INTO profiles (user_id, photo)
        VALUES (?, ?)
    ''', (user_id, photo_id))
    conn.commit()
    
    await message.answer("✅ Фото сохранено!\nТеперь напиши /name Имя")

@dp.message(Command("name"))
async def set_name(message: Message):
    name = message.text.replace("/name", "").strip()
    if name:
        user_id = message.from_user.id
        cursor.execute('UPDATE profiles SET name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        await message.answer(f"✅ Имя '{name}' сохранено!")
    else:
        await message.answer("❌ Напиши: /name ТвоеИмя")

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот запущен!")
    print("📱 Кнопки:")
    print("   - Моя анкета")
    print("   - Смотреть")
    print("   - Премиум")
    print("   - Статистика")
    print("   - Помощь")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
