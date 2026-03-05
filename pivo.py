import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== СТИЛЬ ПИВЧИК ==========
STYLE = {
    "name": "🍺 ПИВЧИК",
    "header": "🍺════════ ПИВЧИК ════════🍺",
    "divider": "──────────────────────────",
    "beer": "🍺",
    "premium": "💎",
    "like": "❤️",
    "mutual": "💕",
    "profile": "👤",
    "view": "👀",
    "stats": "📊",
    "settings": "⚙️",
    "help": "❓",
    "balance": "💰",
    "back": "◀️",
    "next": "▶️",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "crown": "👑",
    "fire": "🔥",
    "gift": "🎁",
    "game": "🎮",
    "chat": "💬",
    "cake": "🎂",
    "map": "📍",
    "sticker": "🎨"
}

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]

FREE_LIMIT = 250
PREMIUM_LIMIT = 1500
MIN_AGE = 18
MAX_AGE = 100

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect("pivchik.db")
cursor = conn.cursor()

# Пользователи
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        is_premium INTEGER DEFAULT 0,
        premium_until TEXT,
        likes_used INTEGER DEFAULT 0,
        views_used INTEGER DEFAULT 0,
        joined_date TEXT,
        balance INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        ban_reason TEXT,
        role TEXT DEFAULT 'user',
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        referral_earnings INTEGER DEFAULT 0,
        city TEXT,
        last_active TEXT,
        notifications_enabled INTEGER DEFAULT 1
    )
''')

# Анкеты
cursor.execute('''
    CREATE TABLE IF NOT EXISTS profiles (
        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        name TEXT,
        age INTEGER,
        gender TEXT,
        city TEXT,
        about TEXT,
        photos TEXT,
        created_at TEXT,
        updated_at TEXT,
        views_count INTEGER DEFAULT 0,
        likes_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        interests TEXT
    )
''')

# Лайки
cursor.execute('''
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        created_at TEXT,
        is_mutual INTEGER DEFAULT 0,
        is_read INTEGER DEFAULT 0,
        UNIQUE(from_user, to_user)
    )
''')

# Просмотры
cursor.execute('''
    CREATE TABLE IF NOT EXISTS views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        viewed_user_id INTEGER,
        viewed_at TEXT,
        UNIQUE(user_id, viewed_user_id)
    )
''')

# Жалобы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        on_user INTEGER,
        reason TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'new'
    )
''')

# Реферальная система
cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        created_at TEXT,
        bonus_given INTEGER DEFAULT 0
    )
''')

# Чаты по интересам
cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        interest TEXT,
        created_at TEXT,
        members_count INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        joined_at TEXT,
        UNIQUE(chat_id, user_id)
    )
''')

# Игры
cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        game_type TEXT,
        status TEXT,
        created_at TEXT,
        completed_at TEXT,
        winner_id INTEGER
    )
''')

# Дни рождения
cursor.execute('''
    CREATE TABLE IF NOT EXISTS birthdays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        birth_date TEXT,
        birth_year INTEGER,
        zodiac TEXT,
        notifications_enabled INTEGER DEFAULT 1
    )
''')

# Стикеры
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        emoji TEXT,
        file_id TEXT,
        price INTEGER DEFAULT 0,
        is_premium INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_stickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sticker_id INTEGER,
        obtained_at TEXT,
        UNIQUE(user_id, sticker_id)
    )
''')

# Создаем начальные комнаты чатов
cursor.execute("SELECT COUNT(*) FROM chat_rooms")
if cursor.fetchone()[0] == 0:
    interests = ["🍺 Пиво", "🎵 Музыка", "🎮 Игры", "🏋️ Спорт", "🎬 Кино", "📚 Книги", "✈️ Путешествия", "🐱 Животные"]
    for interest in interests:
        cursor.execute('''
            INSERT INTO chat_rooms (name, interest, created_at)
            VALUES (?, ?, ?)
        ''', (f"Чат про {interest}", interest, datetime.now().isoformat()))
    conn.commit()

conn.commit()

# ========== FSM ==========
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    about = State()
    photo = State()
    photos = State()

class EditProfileStates(StatesGroup):
    field = State()
    value = State()

class ComplaintStates(StatesGroup):
    reason = State()

class AdminStates(StatesGroup):
    broadcast = State()
    ban_reason = State()
    user_id = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Главная клавиатура"""
    kb = [
        [KeyboardButton(text=f"👤 МОЯ АНКЕТА"), KeyboardButton(text=f"👀 СМОТРЕТЬ")],
        [KeyboardButton(text=f"💎 ПРЕМИУМ"), KeyboardButton(text=f"📊 СТАТИСТИКА")],
        [KeyboardButton(text=f"🔥 ТОП"), KeyboardButton(text=f"🎁 РЕФЕРАЛЫ")],
        [KeyboardButton(text=f"🎮 ИГРЫ"), KeyboardButton(text=f"💬 ЧАТЫ")],
        [KeyboardButton(text=f"🎂 ДНИ РОЖДЕНИЯ"), KeyboardButton(text=f"📍 ПОИСК РЯДОМ")],
        [KeyboardButton(text=f"🎨 СТИКЕРЫ"), KeyboardButton(text=f"⚙️ НАСТРОЙКИ")],
        [KeyboardButton(text=f"💰 БАЛАНС"), KeyboardButton(text=f"❓ ПОМОЩЬ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    kb = [[KeyboardButton(text=f"◀️ НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    """Клавиатура выбора пола"""
    kb = [
        [KeyboardButton(text="МУЖСКОЙ"), KeyboardButton(text="ЖЕНСКИЙ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Проверка на бан
    cursor.execute('SELECT is_banned, ban_reason FROM users WHERE user_id = ?', (user_id,))
    banned = cursor.fetchone()
    if banned and banned[0] == 1:
        await message.answer(f"❌ ВЫ ЗАБЛОКИРОВАНЫ!\nПричина: {banned[1]}")
        return
    
    # Генерация реферального кода
    referral_code = f"PIV{user_id}{random.randint(1000, 9999)}"
    
    # Регистрируем пользователя
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, joined_date, balance, referral_code, last_active, notifications_enabled)
        VALUES (?, ?, ?, ?, 0, ?, ?, 1)
    ''', (user_id, message.from_user.username, message.from_user.first_name, 
          datetime.now().isoformat(), referral_code, datetime.now().isoformat()))
    conn.commit()
    
    # Проверяем реферальный код в параметрах
    args = message.text.split()
    if len(args) > 1:
        ref_code = args[1]
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
        referrer = cursor.fetchone()
        if referrer and referrer[0] != user_id:
            cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, created_at)
                VALUES (?, ?, ?)
            ''', (referrer[0], user_id, datetime.now().isoformat()))
            
            cursor.execute('''
                UPDATE users SET 
                    referral_count = referral_count + 1,
                    balance = balance + 50,
                    referral_earnings = referral_earnings + 50
                WHERE user_id = ?
            ''', (referrer[0],))
            
            cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (referrer[0], user_id))
            conn.commit()
            
            await bot.send_message(
                referrer[0],
                f"🎁 ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ!\n\n"
                f"Новый пользователь @{message.from_user.username}\n"
                f"Начислено 50 ⭐ на баланс!"
            )
    
    # Приветствие
    welcome_text = f"""
{STYLE['header']}

🍺 {message.from_user.first_name}, добро пожаловать в ПИВЧИК!

🚀 ЧТО ТЕБЯ ЖДЕТ:
👤 МОЯ АНКЕТА - создай и управляй
👀 СМОТРЕТЬ - листай анкеты
❤️ ЛАЙКИ - ставь и получай
💎 ПРЕМИУМ - больше возможностей
🔥 ТОП - самые популярные
🎁 РЕФЕРАЛЫ - приглашай друзей

👇 ЖМИ КНОПКИ ВНИЗУ!
{STYLE['divider']}
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== 👤 МОЯ АНКЕТА ==========
@dp.message(F.text.in_(["👤 МОЯ АНКЕТА", "МОЯ АНКЕТА"]))
async def my_profile(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = 1', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            f"❌ У тебя ещё нет анкеты!\n"
            f"Нажми /create чтобы создать анкету"
        )
        return
    
    cursor.execute('SELECT COUNT(*) FROM views WHERE viewed_user_id = ?', (user_id,))
    views = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM likes WHERE to_user = ?', (user_id,))
    likes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id))
    mutual = cursor.fetchone()[0]
    
    cursor.execute('SELECT is_premium FROM users WHERE user_id = ?', (user_id,))
    is_premium = cursor.fetchone()[0]
    premium_badge = f" 💎" if is_premium else ""
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    text = f"""
{STYLE['divider']}
👤 ТВОЯ АНКЕТА{premium_badge}
{STYLE['divider']}

👤 Имя: {profile[2]}
📅 Возраст: {profile[3]}
⚥ Пол: {profile[4]}
🏙 Город: {profile[5]}

📝 О себе:
{profile[6]}

📸 Фото: {len(photos)} шт.

{STYLE['divider']}
📊 СТАТИСТИКА:
👁 Просмотров: {views}
❤️ Лайков: {likes}
💕 Взаимных: {mutual}
📅 Создана: {profile[8][:10]}
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✏️ РЕДАКТИРОВАТЬ", callback_data="edit_profile_menu")
    builder.button(text=f"📸 ДОБАВИТЬ ФОТО", callback_data="add_photo")
    builder.button(text=f"🗑 УДАЛИТЬ", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if main_photo:
        await message.answer_photo(
            photo=main_photo,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== 👀 СМОТРЕТЬ ==========
@dp.message(F.text.in_(["👀 СМОТРЕТЬ", "СМОТРЕТЬ"]))
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ? AND is_active = 1', (user_id,))
    if not cursor.fetchone():
        await message.answer(f"❌ Сначала создай анкету через /create")
        return
    
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    is_premium = user[0]
    views_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(
            f"❌ Лимит просмотров исчерпан ({limit})\n"
            f"Купи 💎 ПРЕМИУМ для увеличения лимита!"
        )
        return
    
    cursor.execute('''
        SELECT p.*, u.username FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id != ? 
        AND p.is_active = 1
        AND u.is_banned = 0
        AND p.user_id NOT IN (
            SELECT viewed_user_id FROM views WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    ''', (user_id, user_id))
    
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            f"🍺 Ты посмотрел все анкеты!\n"
            f"Заходи позже, появятся новые"
        )
        return
    
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    conn.commit()
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    gender_emoji = "👨" if profile[4] == "Мужской" else "👩"
    text = f"""
{STYLE['divider']}
{gender_emoji} {profile[2]}, {profile[3]}
🏙 {profile[5]}

📝 {profile[6]}

❤️ {profile[10]} лайков | 👁 {profile[9]} просмотров
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"❤️ ЛАЙК", callback_data=f"like_{profile[1]}")
    builder.button(text=f"▶️ ДАЛЬШЕ", callback_data="next_profile")
    builder.button(text=f"⚠️ ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    if profile[-1]:
        builder.button(text=f"📱 НАПИСАТЬ", url=f"https://t.me/{profile[-1]}")
    builder.adjust(2, 1, 1)
    
    if main_photo:
        await message.answer_photo(
            photo=main_photo,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_profile")
async def next_profile(callback: CallbackQuery):
    await callback.message.delete()
    await view_profiles(callback.message)

# ========== 💎 ПРЕМИУМ ==========
@dp.message(F.text.in_(["💎 ПРЕМИУМ", "ПРЕМИУМ"]))
async def show_premium(message: Message):
    text = f"""
{STYLE['divider']}
💎 ПРЕМИУМ ПИВЧИК
{STYLE['divider']}

📊 ЛИМИТЫ:
• Бесплатно: {FREE_LIMIT} 👁/❤️
• Премиум: {PREMIUM_LIMIT} 👁/❤️

✨ БОНУСЫ ПРЕМИУМ:
• Приоритетный показ анкеты
• Специальный значок 💎
• Ранний доступ к новым функциям
• Доступ к эксклюзивным стикерам

💰 ЦЕНА:
• 50 ⭐ = 1 день
• 250 ⭐ = 7 дней
• 1000 ⭐ = 30 дней
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 Stars (1 день)", callback_data="buy_50")
    builder.button(text="⭐ 250 Stars (7 дней)", callback_data="buy_250")
    builder.button(text="⭐ 1000 Stars (30 дней)", callback_data="buy_1000")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 🔥 ТОП ==========
@dp.message(F.text.in_(["🔥 ТОП", "ТОП"]))
async def show_top(message: Message):
    # Топ по лайкам
    cursor.execute('''
        SELECT u.user_id, p.name, p.likes_count, p.photos 
        FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.is_active = 1
        ORDER BY p.likes_count DESC
        LIMIT 10
    ''')
    top_likes = cursor.fetchall()
    
    # Топ по просмотрам
    cursor.execute('''
        SELECT u.user_id, p.name, p.views_count, p.photos 
        FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.is_active = 1
        ORDER BY p.views_count DESC
        LIMIT 10
    ''')
    top_views = cursor.fetchall()
    
    text = f"""
{STYLE['divider']}
🔥 ТОП-ЧАРТ ПИВЧИК
{STYLE['divider']}

❤️ ТОП ПО ЛАЙКАМ:
"""
    
    for i, profile in enumerate(top_likes[:5], 1):
        text += f"{i}. {profile[1]} - {profile[2]} ❤️\n"
    
    text += f"\n👁 ТОП ПО ПРОСМОТРАМ:\n"
    
    for i, profile in enumerate(top_views[:5], 1):
        text += f"{i}. {profile[1]} - {profile[2]} 👁\n"
    
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text)

# ========== 🎁 РЕФЕРАЛЫ ==========
@dp.message(F.text.in_(["🎁 РЕФЕРАЛЫ", "РЕФЕРАЛЫ"]))
async def show_referrals(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT referral_code, referral_count, referral_earnings 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    data = cursor.fetchone()
    
    if not data:
        return
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={data[0]}"
    
    text = f"""
{STYLE['divider']}
🎁 РЕФЕРАЛЬНАЯ СИСТЕМА
{STYLE['divider']}

📊 ТВОЯ СТАТИСТИКА:
• Приглашено: {data[1]} чел.
• Заработано: {data[2]} ⭐

💰 БОНУСЫ:
• За каждого друга: 50 ⭐
• За 10 друзей: + 1 день ПРЕМИУМ
• За 50 друзей: + 7 дней ПРЕМИУМ

🔗 ТВОЯ ССЫЛКА:
{referral_link}

{STYLE['divider']}
"""
    
    await message.answer(text)

# ========== 🎮 ИГРЫ ==========
@dp.message(F.text.in_(["🎮 ИГРЫ", "ИГРЫ"]))
async def show_games(message: Message):
    text = f"""
{STYLE['divider']}
🎮 ИГРЫ ДЛЯ ЗНАКОМСТВ
{STYLE['divider']}

Выбери игру:

🎲 КТО Я?
Угадай персонажа по описанию

🎯 УГАДАЙ ЧИСЛО
От 1 до 100, 5 попыток

💕 ЛЮБОВНАЯ ВИКТОРИНА
Узнай совместимость

🎨 НАРИСУЙ ЭМОЦИЮ
Угадай по смайликам

Играй с новыми знакомыми и узнавай друг друга лучше!

{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 КТО Я?", callback_data="game_whoami")
    builder.button(text="🎯 УГАДАЙ ЧИСЛО", callback_data="game_number")
    builder.button(text="💕 ЛЮБОВНАЯ ВИКТОРИНА", callback_data="game_love")
    builder.button(text="🎨 НАРИСУЙ ЭМОЦИЮ", callback_data="game_emoji")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 💬 ЧАТЫ ==========
@dp.message(F.text.in_(["💬 ЧАТЫ", "ЧАТЫ"]))
async def show_chats(message: Message):
    cursor.execute('SELECT id, name, interest, members_count FROM chat_rooms')
    chats = cursor.fetchall()
    
    text = f"""
{STYLE['divider']}
💬 ЧАТЫ ПО ИНТЕРЕСАМ
{STYLE['divider']}

Выбери чат по душе:
"""
    
    builder = InlineKeyboardBuilder()
    for chat in chats:
        text += f"\n{chat[2]} {chat[1]} - {chat[3]} 👥"
        builder.button(text=f"{chat[2]} {chat[1]}", callback_data=f"chat_{chat[0]}")
    
    builder.adjust(2)
    text += f"\n\n{STYLE['divider']}"
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 🎂 ДНИ РОЖДЕНИЯ ==========
@dp.message(F.text.in_(["🎂 ДНИ РОЖДЕНИЯ", "ДНИ РОЖДЕНИЯ"]))
async def show_birthdays(message: Message):
    today = datetime.now()
    
    # Ищем именинников на сегодня
    cursor.execute('''
        SELECT u.user_id, u.first_name, b.birth_date, b.zodiac 
        FROM birthdays b
        JOIN users u ON b.user_id = u.user_id
        WHERE strftime('%m-%d', b.birth_date) = ?
    ''', (today.strftime("%m-%d"),))
    
    birthdays_today = cursor.fetchall()
    
    text = f"""
{STYLE['divider']}
🎂 ДНИ РОЖДЕНИЯ
{STYLE['divider']}

📅 СЕГОДНЯ:
"""
    
    if birthdays_today:
        for b in birthdays_today:
            text += f"🎂 {b[1]} - {b[3]}\n"
    else:
        text += "Сегодня именинников нет\n"
    
    text += f"\n📅 БЛИЖАЙШИЕ:\n"
    
    # Ищем ближайшие дни рождения
    cursor.execute('''
        SELECT u.first_name, b.birth_date, b.zodiac 
        FROM birthdays b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY 
            CASE 
                WHEN substr(b.birth_date, 6) >= ? THEN substr(b.birth_date, 6)
                ELSE substr(b.birth_date, 6) || '2000'
            END
        LIMIT 5
    ''', (today.strftime("%m-%d"),))
    
    upcoming = cursor.fetchall()
    for u in upcoming:
        birth_date = datetime.strptime(u[1], "%d.%m.%Y")
        text += f"📅 {u[0]} - {u[2]} ({birth_date.strftime('%d.%m')})\n"
    
    text += f"\nЧтобы добавить свой день рождения:\n/setbirthday 01.01.1990"
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text)

@dp.message(Command("setbirthday"))
async def set_birthday(message: Message):
    try:
        date_str = message.text.replace("/setbirthday", "").strip()
        birth_date = datetime.strptime(date_str, "%d.%m.%Y")
        
        # Определяем знак зодиака
        zodiac = get_zodiac(birth_date)
        
        cursor.execute('''
            INSERT OR REPLACE INTO birthdays 
            (user_id, birth_date, birth_year, zodiac, notifications_enabled)
            VALUES (?, ?, ?, ?, 1)
        ''', (message.from_user.id, date_str, birth_date.year, zodiac))
        conn.commit()
        
        # Обновляем возраст в анкете
        age = (datetime.now() - birth_date).days // 365
        cursor.execute('UPDATE profiles SET age = ? WHERE user_id = ?', (age, message.from_user.id))
        conn.commit()
        
        await message.answer(
            f"✅ День рождения сохранен!\n"
            f"Знак зодиака: {zodiac}\n"
            f"Возраст обновлен: {age}"
        )
        
    except Exception as e:
        await message.answer("❌ Неверный формат. Используй: /setbirthday 01.01.1990")

def get_zodiac(date):
    day, month = date.day, date.month
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "♈ Овен"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "♉ Телец"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "♊ Близнецы"
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "♋ Рак"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "♌ Лев"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "♍ Дева"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "♎ Весы"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "♏ Скорпион"
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return "♐ Стрелец"
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "♑ Козерог"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "♒ Водолей"
    else:
        return "♓ Рыбы"

# ========== 📍 ПОИСК РЯДОМ ==========
@dp.message(F.text.in_(["📍 ПОИСК РЯДОМ", "ПОИСК РЯДОМ"]))
async def find_nearby(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT city FROM users WHERE user_id = ?', (user_id,))
    user_city = cursor.fetchone()
    
    if not user_city or not user_city[0]:
        await message.answer(
            f"⚠️ Укажи свой город в настройках!\n"
            f"Используй команду /setcity НазваниеГорода"
        )
        return
    
    cursor.execute('''
        SELECT u.user_id, p.name, p.age, p.gender, p.photos 
        FROM users u
        JOIN profiles p ON u.user_id = p.user_id
        WHERE u.city = ? AND u.user_id != ? AND p.is_active = 1
        ORDER BY RANDOM()
        LIMIT 5
    ''', (user_city[0], user_id))
    
    nearby = cursor.fetchall()
    
    if not nearby:
        await message.answer(
            f"❌ В твоем городе пока никого нет :(\n"
            f"Пригласи друзей через реферальную систему!"
        )
        return
    
    text = f"{STYLE['divider']}\n📍 ЛЮДИ РЯДОМ\n{STYLE['divider']}\n\n"
    
    for person in nearby[:5]:
        gender_emoji = "👨" if person[3] == "Мужской" else "👩"
        text += f"{gender_emoji} {person[1]}, {person[2]}\n"
    
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text)

@dp.message(Command("setcity"))
async def set_city(message: Message):
    city = message.text.replace("/setcity", "").strip()
    if not city:
        await message.answer("❌ Напиши: /setcity НазваниеГорода")
        return
    
    cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (city, message.from_user.id))
    conn.commit()
    
    await message.answer(f"✅ Город {city} сохранен!")

# ========== 🎨 СТИКЕРЫ ==========
@dp.message(F.text.in_(["🎨 СТИКЕРЫ", "СТИКЕРЫ"]))
async def show_stickers(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT s.id, s.name, s.emoji, s.price, s.is_premium,
               CASE WHEN us.id IS NOT NULL THEN 1 ELSE 0 END as owned
        FROM stickers s
        LEFT JOIN user_stickers us ON s.id = us.sticker_id AND us.user_id = ?
        ORDER BY s.is_premium, s.price
    ''', (user_id,))
    
    stickers = cursor.fetchall()
    
    text = f"""
{STYLE['divider']}
🎨 КОЛЛЕКЦИЯ СТИКЕРОВ
{STYLE['divider']}

"""
    
    builder = InlineKeyboardBuilder()
    for sticker in stickers:
        status = "✅" if sticker[5] else "❌"
        price_info = f"{sticker[3]} ⭐" if sticker[3] > 0 else "Бесплатно"
        premium_info = " 💎" if sticker[4] else ""
        
        text += f"{status} {sticker[2]} {sticker[1]}{premium_info} - {price_info}\n"
        
        if not sticker[5]:
            builder.button(text=f"Купить {sticker[2]}", callback_data=f"buy_sticker_{sticker[0]}")
    
    builder.adjust(2)
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 📊 СТАТИСТИКА ==========
@dp.message(F.text.in_(["📊 СТАТИСТИКА", "СТАТИСТИКА"]))
async def show_stats(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT 
            u.is_premium,
            u.views_used,
            u.likes_used,
            (SELECT COUNT(*) FROM views WHERE user_id = ?) as viewed_count,
            (SELECT COUNT(*) FROM views WHERE viewed_user_id = ?) as my_views,
            (SELECT COUNT(*) FROM likes WHERE from_user = ?) as likes_given,
            (SELECT COUNT(*) FROM likes WHERE to_user = ?) as likes_received,
            (SELECT COUNT(*) FROM likes WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)) as mutual_count
        FROM users u
        WHERE u.user_id = ?
    ''', (user_id, user_id, user_id, user_id, user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        is_premium, views_used, likes_used, viewed_count, my_views, likes_given, likes_received, mutual_count = stats
        limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
        
        text = f"""
{STYLE['divider']}
📊 ТВОЯ СТАТИСТИКА
{STYLE['divider']}

👁 ТЫ ПОСМОТРЕЛ: {viewed_count}
👁 ТЕБЯ ПОСМОТРЕЛИ: {my_views}
❤️ ТЫ ЛАЙКНУЛ: {likes_given}
❤️ ТЕБЯ ЛАЙКНУЛИ: {likes_received}
💕 ВЗАИМНЫХ: {mutual_count}

📈 ОСТАЛОСЬ:
• 👁 {limit - views_used}
• ❤️ {limit - likes_used}
{STYLE['divider']}
"""
        
        await message.answer(text)

# ========== ЛАЙКИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer(f"❌ Нельзя лайкнуть себя!", show_alert=True)
        return
    
    cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,))
    user = cursor.fetchone()
    is_premium = user[0]
    likes_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит лайков ({limit}) исчерпан!", show_alert=True)
        return
    
    try:
        cursor.execute('''
            INSERT INTO likes (from_user, to_user, created_at)
            VALUES (?, ?, ?)
        ''', (from_user, to_user, datetime.now().isoformat()))
        
        cursor.execute('UPDATE users SET likes_used = likes_used + 1 WHERE user_id = ?', (from_user,))
        cursor.execute('UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
        conn.commit()
        
        cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user))
        
        if cursor.fetchone():
            cursor.execute('''
                UPDATE likes SET is_mutual = 1 
                WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ''', (from_user, to_user, to_user, from_user))
            conn.commit()
            
            await callback.answer(f"💕 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (to_user,))
            to_username = cursor.fetchone()[0]
            
            builder1 = InlineKeyboardBuilder()
            if to_username:
                builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
            builder1.button(text=f"👀 ПРОДОЛЖИТЬ", callback_data="next_profile")
            builder1.adjust(1)
            
            await bot.send_message(
                from_user,
                f"{STYLE['divider']}\n"
                f"💕 ВЗАИМНЫЙ ЛАЙК!\n"
                f"{STYLE['divider']}\n\n"
                f"Ты понравился {to_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder1.as_markup()
            )
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (from_user,))
            from_username = cursor.fetchone()[0]
            
            builder2 = InlineKeyboardBuilder()
            if from_username:
                builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
            builder2.button(text=f"👀 ПРОДОЛЖИТЬ", callback_data="next_profile")
            builder2.adjust(1)
            
            await bot.send_message(
                to_user,
                f"{STYLE['divider']}\n"
                f"💕 ВЗАИМНЫЙ ЛАЙК!\n"
                f"{STYLE['divider']}\n\n"
                f"Ты понравился {from_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder2.as_markup()
            )
            
        else:
            await callback.answer(f"❤️ ЛАЙК ОТПРАВЛЕН!")
            
    except sqlite3.IntegrityError:
        await callback.answer(f"❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ? AND is_active = 1', (user_id,))
    if cursor.fetchone():
        await message.answer(
            f"❌ У тебя уже есть активная анкета!\n"
            f"Если хочешь создать новую, сначала удали старую."
        )
        return
    
    await message.answer(
        f"{STYLE['divider']}\n"
        f"🍺 СОЗДАНИЕ АНКЕТЫ\n"
        f"{STYLE['divider']}\n\n"
        f"Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer(f"❌ Слишком длинное имя. Максимум 50 символов.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        f"📅 Сколько тебе лет? (от {MIN_AGE} до {MAX_AGE})",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.age)

@dp.message(ProfileStates.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < MIN_AGE or age > MAX_AGE:
            raise ValueError
    except:
        await message.answer(f"❌ Введи число от {MIN_AGE} до {MAX_AGE}")
        return
    
    await state.update_data(age=age)
    await message.answer(
        "👤 Выбери пол:",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(ProfileStates.gender)

@dp.message(ProfileStates.gender)
async def process_gender(message: Message, state: FSMContext):
    if message.text.upper() not in ["МУЖСКОЙ", "ЖЕНСКИЙ"]:
        await message.answer("❌ Используй кнопки")
        return
    
    gender = "Мужской" if message.text.upper() == "МУЖСКОЙ" else "Женский"
    await state.update_data(gender=gender)
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer(f"❌ Слишком длинное название города")
        return
    
    await state.update_data(city=message.text)
    await message.answer(
        f"📝 Напиши о себе\n"
        f"(чем увлекаешься, что ищешь)\n\n"
        f"⚠️ Без ссылок и юзернеймов!",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(f"❌ Ссылки и юзернеймы запрещены!")
        return
    
    if len(message.text) > 500:
        await message.answer(f"❌ Слишком длинное описание. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь свое фото\n"
        f"(можно добавить еще фото позже)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    photos = json.dumps([photo_id])
    
    cursor.execute('''
        INSERT INTO profiles 
        (user_id, name, age, gender, city, about, photos, created_at, updated_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (
        message.from_user.id,
        data['name'],
        data['age'],
        data['gender'],
        data['city'],
        data['about'],
        photos,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    conn.commit()
    
    await state.clear()
    await message.answer(
        f"{STYLE['divider']}\n"
        f"✅ АНКЕТА СОЗДАНА!\n"
        f"{STYLE['divider']}\n\n"
        f"Теперь можно смотреть анкеты 👀",
        reply_markup=get_main_keyboard()
    )

# ========== НАЗАД ==========
@dp.message(F.text.in_(["◀️ НАЗАД", "НАЗАД"]))
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# ========== ПОМОЩЬ ==========
@dp.message(F.text.in_(["❓ ПОМОЩЬ", "ПОМОЩЬ"]))
async def show_help(message: Message):
    text = f"""
{STYLE['divider']}
❓ ПОМОЩЬ
{STYLE['divider']}

🍺 КАК ПОЛЬЗОВАТЬСЯ:

/create - создать анкету
/addphoto - добавить фото
/setcity - указать город
/setbirthday - указать день рождения

👤 МОЯ АНКЕТА - просмотр и редактирование
👀 СМОТРЕТЬ - листать анкеты
❤️ ЛАЙК - поставить лайк
💕 ВЗАИМНЫЙ ЛАЙК - можно писать

🔥 ТОП - самые популярные
🎁 РЕФЕРАЛЫ - приглашай друзей
🎮 ИГРЫ - игры для знакомств
💬 ЧАТЫ - общение по интересам

📊 КОМАНДЫ:
/premium - купить премиум
/stats - статистика

⚠️ ПРАВИЛА:
• Только реальные фото
• Без оскорблений
• Без спама
• Возраст 18+

👨‍💻 По вопросам: @admin
{STYLE['divider']}
"""
    await message.answer(text)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
{STYLE['header']}
{STYLE['beer']} ПИВЧИК ЗАПУЩЕН!
{STYLE['beer']} АДМИН: {ADMIN_IDS[0]}
{STYLE['beer']} СТАТУС: ВСЕ РАБОТАЕТ
{STYLE['beer']} ФИЧИ: 10/10
{STYLE['header']}
""")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
