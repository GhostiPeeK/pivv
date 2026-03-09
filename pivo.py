import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== МИНИМАЛИСТИЧНЫЙ КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_ID = 2091630272

FREE_LIMIT = 250
PREMIUM_LIMIT = 1500
MIN_AGE = 18

# ========== МИНИМАЛИСТИЧНАЯ БАЗА ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("pivchik.db")
        self.cursor = self.conn.cursor()
        self.create_tables()
        print("💾 БАЗА ГОТОВА")
    
    def create_tables(self):
        # Только самое важное
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                age INTEGER,
                city TEXT,
                about TEXT,
                photo TEXT,
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                likes_used INTEGER DEFAULT 0,
                views_used INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                is_mutual INTEGER DEFAULT 0,
                UNIQUE(from_user, to_user)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                viewed_user_id INTEGER,
                UNIQUE(user_id, viewed_user_id)
            )
        ''')
        self.conn.commit()

db = Database()

# ========== FSM ==========
class CreateProfile(StatesGroup):
    name = State()
    age = State()
    city = State()
    about = State()
    photo = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== МИНИМАЛИСТИЧНАЯ КЛАВИАТУРА ==========
def get_menu():
    """Только 6 кнопок — идеально"""
    kb = [
        [KeyboardButton(text="👤 Я"), KeyboardButton(text="👀 Смотреть")],
        [KeyboardButton(text="⭐ Топ"), KeyboardButton(text="📊 Мое")],
        [KeyboardButton(text="💎 Premium"), KeyboardButton(text="❓ ?")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def back():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="← Назад")]], resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    
    # Проверяем есть ли юзер
    user = db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if not user:
        db.cursor.execute('''
            INSERT INTO users (user_id, username, balance)
            VALUES (?, ?, 0)
        ''', (user_id, message.from_user.username))
        db.conn.commit()
    
    await message.answer(
        f"🍺 ПИВЧИК\n\n"
        f"привет, {message.from_user.first_name}\n\n"
        f"👤 Я — твоя анкета\n"
        f"👀 Смотреть — люди рядом\n"
        f"⭐ Топ — лучшие\n"
        f"📊 Мое — статистика\n"
        f"💎 Premium — больше\n"
        f"❓ ? — помощь",
        reply_markup=get_menu()
    )

# ========== 👤 Я (ПРОФИЛЬ) ==========
@dp.message(F.text == "👤 Я")
async def my_profile(message: Message):
    user_id = message.from_user.id
    user = db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    
    if not user or not user[2]:  # нет имени = нет анкеты
        await message.answer("❌ анкеты нет\nнапиши /create")
        return
    
    text = f"""
👤 {user[2]}, {user[3]}
📍 {user[4]}
📝 {user[5]}

👁 {user[11]} | ❤️ {user[10]}
"""
    if user[6]:
        await message.answer_photo(photo=user[6], caption=text)
    else:
        await message.answer(text)

# ========== 👀 СМОТРЕТЬ ==========
@dp.message(F.text == "👀 Смотреть")
async def view(message: Message):
    user_id = message.from_user.id
    user = db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    
    if not user or not user[2]:
        await message.answer("❌ сначала создай анкету\n/create")
        return
    
    # Лимиты
    limit = PREMIUM_LIMIT if user[7] else FREE_LIMIT
    if user[9] >= limit:
        await message.answer("❌ лимит на сегодня\n💎 Premium снимает лимиты")
        return
    
    # Ищем кого не смотрел
    candidates = db.cursor.execute('''
        SELECT * FROM users 
        WHERE user_id != ? 
        AND user_id NOT IN (SELECT viewed_user_id FROM views WHERE user_id = ?)
        AND name IS NOT NULL
        ORDER BY RANDOM() LIMIT 1
    ''', (user_id, user_id)).fetchone()
    
    if not candidates:
        await message.answer("🎉 ты всех посмотрел!")
        return
    
    # Сохраняем просмотр
    db.cursor.execute('INSERT INTO views (user_id, viewed_user_id) VALUES (?, ?)', (user_id, candidates[0]))
    db.cursor.execute('UPDATE users SET views_used = views_used + 1, views_count = views_count + 1 WHERE user_id = ?', (user_id,))
    db.cursor.execute('UPDATE users SET views_count = views_count + 1 WHERE user_id = ?', (candidates[0],))
    db.conn.commit()
    
    text = f"""
👤 {candidates[2]}, {candidates[3]}
📍 {candidates[4]}
📝 {candidates[5]}

❤️ {candidates[11]}
"""
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❤️", callback_data=f"like_{candidates[0]}")
    kb.button(text="→", callback_data="next")
    
    await message.answer_photo(photo=candidates[6], caption=text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "next")
async def next_profile(callback: CallbackQuery):
    await callback.message.delete()
    await view(callback.message)

# ========== ❤️ ЛАЙКИ (С КНОПКОЙ ПОСЛЕ ВЗАИМКИ) ==========
@dp.callback_query(F.data.startswith("like_"))
async def like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer("❌ себя нельзя", show_alert=True)
        return
    
    # Проверка лимита
    user = db.cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,)).fetchone()
    limit = PREMIUM_LIMIT if user[0] else FREE_LIMIT
    if user[1] >= limit:
        await callback.answer("❌ лимит исчерпан", show_alert=True)
        return
    
    try:
        db.cursor.execute('INSERT INTO likes (from_user, to_user) VALUES (?, ?)', (from_user, to_user))
        db.cursor.execute('UPDATE users SET likes_used = likes_used + 1, likes_count = likes_count + 1 WHERE user_id = ?', (from_user,))
        db.cursor.execute('UPDATE users SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
        db.conn.commit()
        
        # Проверка взаимности
        mutual = db.cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user)).fetchone()
        
        if mutual:
            db.cursor.execute('UPDATE likes SET is_mutual = 1 WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)', 
                            (from_user, to_user, to_user, from_user))
            db.conn.commit()
            
            # Получаем инфу о том, кого лайкнули
            to_user_data = db.cursor.execute('SELECT username, name FROM users WHERE user_id = ?', (to_user,)).fetchone()
            to_username = to_user_data[0]
            to_name = to_user_data[1]
            
            # Получаем инфу о том, кто лайкнул
            from_user_data = db.cursor.execute('SELECT username, name FROM users WHERE user_id = ?', (from_user,)).fetchone()
            from_username = from_user_data[0]
            from_name = from_user_data[1]
            
            await callback.answer("💕 ВЗАИМНО!", show_alert=True)
            
            # КНОПКА ДЛЯ ПЕРВОГО — написать второму
            if to_username:
                kb1 = InlineKeyboardBuilder()
                kb1.button(text=f"💬 Написать {to_name}", url=f"https://t.me/{to_username}")
                
                await bot.send_message(
                    from_user,
                    f"💕 Взаимный интерес с {to_name}!\n\nМожешь написать ей/ему:",
                    reply_markup=kb1.as_markup()
                )
            else:
                await bot.send_message(
                    from_user,
                    f"💕 Взаимный интерес с {to_name}!\n\nК сожалению, у {to_name} нет username, но вы в ЛС не напишете."
                )
            
            # КНОПКА ДЛЯ ВТОРОГО — написать первому
            if from_username:
                kb2 = InlineKeyboardBuilder()
                kb2.button(text=f"💬 Написать {from_name}", url=f"https://t.me/{from_username}")
                
                await bot.send_message(
                    to_user,
                    f"💕 Взаимный интерес с {from_name}!\n\nМожешь написать ей/ему:",
                    reply_markup=kb2.as_markup()
                )
            else:
                await bot.send_message(
                    to_user,
                    f"💕 Взаимный интерес с {from_name}!\n\nК сожалению, у {from_name} нет username."
                )
        else:
            await callback.answer("❤️")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ уже было", show_alert=True)

# ========== ⭐ ТОП ==========
@dp.message(F.text == "⭐ Топ")
async def top(message: Message):
    top_likes = db.cursor.execute('''
        SELECT name, likes_count FROM users 
        WHERE name IS NOT NULL 
        ORDER BY likes_count DESC LIMIT 5
    ''').fetchall()
    
    top_views = db.cursor.execute('''
        SELECT name, views_count FROM users 
        WHERE name IS NOT NULL 
        ORDER BY views_count DESC LIMIT 5
    ''').fetchall()
    
    text = "⭐ ТОП\n\n❤️ Лайки:\n"
    for i, (name, count) in enumerate(top_likes, 1):
        text += f"{i}. {name} — {count}\n"
    
    text += "\n👁 Просмотры:\n"
    for i, (name, count) in enumerate(top_views, 1):
        text += f"{i}. {name} — {count}\n"
    
    await message.answer(text)

# ========== 📊 МОЕ ==========
@dp.message(F.text == "📊 Мое")
async def my_stats(message: Message):
    user_id = message.from_user.id
    user = db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    
    if not user:
        return
    
    limit = PREMIUM_LIMIT if user[7] else FREE_LIMIT
    
    text = f"""
📊 {user[2] or 'Без имени'}

👁 просмотров: {user[11]}
❤️ лайков: {user[10]}
💕 взаимных: {db.cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]}

📈 сегодня: {user[9]}/{limit} 👁 | {user[8]}/{limit} ❤️
💰 баланс: {user[12]} ⭐
"""
    await message.answer(text)

# ========== 💎 PREMIUM ==========
@dp.message(F.text == "💎 Premium")
async def premium(message: Message):
    text = f"""
💎 PREMIUM

• {PREMIUM_LIMIT} 👁/❤️ вместо {FREE_LIMIT}
• значок в профиле
• без рекламы

💰 50 ⭐ = 1 день
250 ⭐ = 7 дней
1000 ⭐ = 30 дней
"""
    kb = InlineKeyboardBuilder()
    kb.button(text="50 ⭐", callback_data="buy_50")
    kb.button(text="250 ⭐", callback_data="buy_250")
    kb.button(text="1000 ⭐", callback_data="buy_1000")
    kb.adjust(3)
    
    await message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    days = amount // 50
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💎 Premium",
        description=f"{days} дней",
        payload=f"premium_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=amount)]
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def paid(message: Message):
    user_id = message.from_user.id
    days = int(message.successful_payment.invoice_payload.split("_")[1])
    
    db.cursor.execute('''
        UPDATE users SET 
            is_premium = 1,
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=days)).isoformat(), user_id))
    db.conn.commit()
    
    await message.answer(f"✅ Premium на {days} дней активирован")

# ========== ❓ ПОМОЩЬ ==========
@dp.message(F.text == "❓ ?")
async def help_msg(message: Message):
    text = """
❓ ПИВЧИК

/create — создать анкету
👤 Я — моя анкета
👀 Смотреть — люди
❤️ — поставить лайк
💕 взаимный — можно писать

всё просто
"""
    await message.answer(text)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    await message.answer("👤 имя?", reply_markup=back())
    await state.set_state(CreateProfile.name)

@dp.message(CreateProfile.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"📅 возраст? (от {MIN_AGE})")
    await state.set_state(CreateProfile.age)

@dp.message(CreateProfile.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < MIN_AGE:
            raise ValueError
    except:
        await message.answer(f"❌ от {MIN_AGE} лет")
        return
    
    await state.update_data(age=age)
    await message.answer("📍 город?")
    await state.set_state(CreateProfile.city)

@dp.message(CreateProfile.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("📝 о себе? (коротко)")
    await state.set_state(CreateProfile.about)

@dp.message(CreateProfile.about)
async def process_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer("📸 фото")
    await state.set_state(CreateProfile.photo)

@dp.message(CreateProfile.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    
    db.cursor.execute('''
        UPDATE users SET 
            name = ?, age = ?, city = ?, about = ?, photo = ?
        WHERE user_id = ?
    ''', (data['name'], data['age'], data['city'], data['about'], message.photo[-1].file_id, user_id))
    db.conn.commit()
    
    await state.clear()
    await message.answer("✅ готово!", reply_markup=get_menu())

# ========== НАЗАД ==========
@dp.message(F.text == "← Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await start(message)

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    users = db.cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    profiles = db.cursor.execute('SELECT COUNT(*) FROM users WHERE name IS NOT NULL').fetchone()[0]
    premium = db.cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1').fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1').fetchone()[0]
    
    await message.answer(f"👑\n👥 {users}\n📝 {profiles}\n💎 {premium}\n💕 {mutual}")

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("\n🍺 ПИВЧИК MINIMAL\n")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
