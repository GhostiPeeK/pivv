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
    LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
        birth_date TEXT,
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
        photos TEXT,  -- JSON массив фото
        created_at TEXT,
        updated_at TEXT,
        views_count INTEGER DEFAULT 0,
        likes_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        interests TEXT,  -- JSON массив интересов
        games_played INTEGER DEFAULT 0,
        games_won INTEGER DEFAULT 0
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
        status TEXT DEFAULT 'new',
        resolved_by INTEGER,
        resolved_at TEXT
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
        winner_id INTEGER,
        user1_score INTEGER DEFAULT 0,
        user2_score INTEGER DEFAULT 0
    )
''')

# Геолокация
cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        user_id INTEGER PRIMARY KEY,
        latitude REAL,
        longitude REAL,
        city TEXT,
        updated_at TEXT,
        is_visible INTEGER DEFAULT 1
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

# Статистика бота
cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE,
        new_users INTEGER DEFAULT 0,
        new_profiles INTEGER DEFAULT 0,
        likes_count INTEGER DEFAULT 0,
        mutual_count INTEGER DEFAULT 0,
        games_played INTEGER DEFAULT 0,
        referrals_count INTEGER DEFAULT 0
    )
''')

# Логи админов
cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target_user INTEGER,
        details TEXT,
        created_at TEXT
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

# Создаем начальные стикеры
cursor.execute("SELECT COUNT(*) FROM stickers")
if cursor.fetchone()[0] == 0:
    default_stickers = [
        ("🍺 Пивной", "🍺", None, 0, 0),
        ("❤️ Сердечный", "❤️", None, 10, 0),
        ("💎 Премиум", "💎", None, 100, 1),
        ("🔥 Огонь", "🔥", None, 20, 0),
        ("🎁 Подарок", "🎁", None, 0, 0)
    ]
    for sticker in default_stickers:
        cursor.execute('''
            INSERT INTO stickers (name, emoji, file_id, price, is_premium)
            VALUES (?, ?, ?, ?, ?)
        ''', sticker)

conn.commit()

# ========== FSM ==========
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    about = State()
    photos = State()
    interests = State()

class EditProfileStates(StatesGroup):
    field = State()
    value = State()

class ComplaintStates(StatesGroup):
    reason = State()

class AdminStates(StatesGroup):
    broadcast = State()
    ban_reason = State()
    user_id = State()

class GameStates(StatesGroup):
    waiting = State()
    playing = State()

class StickerStates(StatesGroup):
    buying = State()
    sending = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Главная клавиатура"""
    kb = [
        [KeyboardButton(text=f"{STYLE['profile']} МОЯ АНКЕТА"), KeyboardButton(text=f"{STYLE['view']} СМОТРЕТЬ")],
        [KeyboardButton(text=f"{STYLE['premium']} ПРЕМИУМ"), KeyboardButton(text=f"{STYLE['stats']} СТАТИСТИКА")],
        [KeyboardButton(text=f"{STYLE['fire']} ТОП"), KeyboardButton(text=f"{STYLE['gift']} РЕФЕРАЛЫ")],
        [KeyboardButton(text=f"{STYLE['game']} ИГРЫ"), KeyboardButton(text=f"{STYLE['chat']} ЧАТЫ")],
        [KeyboardButton(text=f"{STYLE['cake']} ДНИ РОЖДЕНИЯ"), KeyboardButton(text=f"{STYLE['map']} ПОИСК РЯДОМ")],
        [KeyboardButton(text=f"{STYLE['sticker']} СТИКЕРЫ"), KeyboardButton(text=f"{STYLE['settings']} НАСТРОЙКИ")],
        [KeyboardButton(text=f"{STYLE['balance']} БАЛАНС"), KeyboardButton(text=f"{STYLE['help']} ПОМОЩЬ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    kb = [[KeyboardButton(text=f"{STYLE['back']} НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    """Клавиатура выбора пола"""
    kb = [
        [KeyboardButton(text="🍺 МУЖСКОЙ"), KeyboardButton(text="🍺 ЖЕНСКИЙ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_interests_keyboard():
    """Клавиатура выбора интересов"""
    interests = ["🍺 Пиво", "🎵 Музыка", "🎮 Игры", "🏋️ Спорт", "🎬 Кино", "📚 Книги", "✈️ Путешествия", "🐱 Животные"]
    kb = []
    row = []
    for i, interest in enumerate(interests):
        row.append(KeyboardButton(text=interest))
        if (i + 1) % 2 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([KeyboardButton(text=f"{STYLE['success']} ГОТОВО")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверка на бан
    cursor.execute('SELECT is_banned, ban_reason FROM users WHERE user_id = ?', (user_id,))
    banned = cursor.fetchone()
    if banned and banned[0] == 1:
        await message.answer(f"{STYLE['error']} ВЫ ЗАБЛОКИРОВАНЫ!\nПричина: {banned[1]}")
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
            # Начисляем бонусы
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
            
            # Уведомление рефереру
            await bot.send_message(
                referrer[0],
                f"{STYLE['gift']} ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ!\n\n"
                f"Новый пользователь @{message.from_user.username}\n"
                f"Начислено 50 ⭐ на баланс!"
            )
    
    # Обновляем статистику
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        INSERT INTO bot_stats (date, new_users) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET new_users = new_users + 1
    ''', (today,))
    conn.commit()
    
    # Приветствие
    welcome_text = f"""
{STYLE['header']}

🍺 {message.from_user.first_name}, добро пожаловать в ПИВЧИК 2.0!
🔞 Новые фичи уже здесь!

🚀 ЧТО ТЕБЯ ЖДЕТ:
{STYLE['profile']} Создай анкету
{STYLE['view']} Смотри анкеты
{STYLE['like']} Ставь лайки
{STYLE['mutual']} Взаимные лайки
{STYLE['fire']} Топ популярных
{STYLE['gift']} Реферальная система
{STYLE['game']} Игры для знакомств
{STYLE['chat']} Чаты по интересам
{STYLE['cake']} Дни рождения
{STYLE['map']} Поиск рядом
{STYLE['sticker']} Коллекция стикеров
{STYLE['premium']} Премиум - больше возможностей

👇 ЖМИ КНОПКИ ВНИЗУ И ПОГНАЛИ!
{STYLE['divider']}
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== 1. 🔔 УВЕДОМЛЕНИЯ О ЛАЙКАХ ==========
async def send_like_notification(to_user: int, from_user: int, from_name: str):
    """Отправка уведомления о новом лайке"""
    cursor.execute('SELECT notifications_enabled FROM users WHERE user_id = ?', (to_user,))
    enabled = cursor.fetchone()
    
    if enabled and enabled[0] == 1:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"{STYLE['profile']} ПОСМОТРЕТЬ", callback_data=f"view_profile_{from_user}")
        
        await bot.send_message(
            to_user,
            f"{STYLE['like']} НОВЫЙ ЛАЙК!\n\n"
            f"@{from_name} лайкнул твою анкету!\n\n"
            f"Посмотри, может это твоя судьба? 💕",
            reply_markup=builder.as_markup()
        )

# ========== 2. 🎁 РЕФЕРАЛЬНАЯ СИСТЕМА ==========
@dp.message(F.text.in_([f"{STYLE['gift']} РЕФЕРАЛЫ", "РЕФЕРАЛЫ"]))
async def show_referrals(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT referral_code, referral_count, referral_earnings 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    data = cursor.fetchone()
    
    if not data:
        return
    
    referral_link = f"https://t.me/{(await bot.get_me()).username}?start={data[0]}"
    
    text = f"""
{STYLE['divider']}
{STYLE['gift']} РЕФЕРАЛЬНАЯ СИСТЕМА
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

# ========== 3. 🌍 ФИЛЬТР ПО ГОРОДАМ ==========
@dp.message(F.text.in_([f"{STYLE['map']} ПОИСК РЯДОМ", "ПОИСК РЯДОМ"]))
async def find_nearby(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT city FROM users WHERE user_id = ?', (user_id,))
    user_city = cursor.fetchone()
    
    if not user_city or not user_city[0]:
        await message.answer(
            f"{STYLE['warning']} Укажи свой город в настройках!\n"
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
            f"{STYLE['error']} В твоем городе пока никого нет :(\n"
            f"Пригласи друзей через реферальную систему!"
        )
        return
    
    text = f"{STYLE['divider']}\n{STYLE['map']} ЛЮДИ РЯДОМ\n{STYLE['divider']}\n\n"
    
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
    
    await message.answer(f"{STYLE['success']} Город {city} сохранен!")

# ========== 4. 🔥 ТОП-ЧАРТ САМЫХ ПОПУЛЯРНЫХ ==========
@dp.message(F.text.in_([f"{STYLE['fire']} ТОП", "ТОП"]))
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
{STYLE['fire']} ТОП-ЧАРТ ПИВЧИК
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

# ========== 5. 📸 НЕСКОЛЬКО ФОТО В АНКЕТУ ==========
@dp.message(Command("addphoto"))
async def add_photo(message: Message, state: FSMContext):
    await message.answer(
        f"{STYLE['divider']}\n"
        f"📸 ДОБАВЛЕНИЕ ФОТО\n"
        f"{STYLE['divider']}\n\n"
        f"Отправь фото для добавления в анкету\n"
        f"(можно добавить до 5 фото)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photos)

@dp.message(ProfileStates.photos, F.photo)
async def process_add_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    
    cursor.execute('SELECT photos FROM profiles WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        photos = json.loads(result[0])
    else:
        photos = []
    
    if len(photos) >= 5:
        await message.answer(f"{STYLE['error']} Максимум 5 фото!")
        return
    
    photos.append(photo_id)
    cursor.execute('UPDATE profiles SET photos = ? WHERE user_id = ?', 
                  (json.dumps(photos), user_id))
    conn.commit()
    
    await message.answer(f"{STYLE['success']} Фото добавлено! ({len(photos)}/5)")
    
    if len(photos) < 5:
        await message.answer("Можешь добавить еще фото или нажми /done")

@dp.message(Command("done"))
async def done_photos(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f"{STYLE['success']} Фото сохранены!", reply_markup=get_main_keyboard())

# ========== 6. 🎮 ИГРЫ ДЛЯ ЗНАКОМСТВ ==========
@dp.message(F.text.in_([f"{STYLE['game']} ИГРЫ", "ИГРЫ"]))
async def show_games(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 Кто я?", callback_data="game_whoami")
    builder.button(text="🎯 Угадай число", callback_data="game_number")
    builder.button(text="💕 Любовная викторина", callback_data="game_love")
    builder.button(text="🎨 Нарисуй эмоцию", callback_data="game_emoji")
    builder.adjust(2)
    
    text = f"""
{STYLE['divider']}
{STYLE['game']} ИГРЫ ДЛЯ ЗНАКОМСТВ
{STYLE['divider']}

Выбери игру:
• 🎲 Кто я? - угадай персонажа
• 🎯 Угадай число - от 1 до 100
• 💕 Любовная викторина - вопросы о тебе
• 🎨 Нарисуй эмоцию - угадай по смайлику

Играй с новыми знакомыми и узнавай друг друга лучше!
{STYLE['divider']}
"""
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("game_"))
async def start_game(callback: CallbackQuery, state: FSMContext):
    game_type = callback.data.replace("game_", "")
    
    # Ищем второго игрока
    cursor.execute('''
        SELECT user_id FROM users 
        WHERE user_id != ? AND is_banned = 0
        ORDER BY RANDOM() LIMIT 1
    ''', (callback.from_user.id,))
    
    opponent = cursor.fetchone()
    
    if not opponent:
        await callback.answer("😕 Нет свободных игроков", show_alert=True)
        return
    
    game_id = random.randint(1000, 9999)
    
    # Создаем игру
    cursor.execute('''
        INSERT INTO games (user1_id, user2_id, game_type, status, created_at)
        VALUES (?, ?, ?, 'waiting', ?)
    ''', (callback.from_user.id, opponent[0], game_type, datetime.now().isoformat()))
    conn.commit()
    
    # Приглашение второму игроку
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 ПРИНЯТЬ ВЫЗОВ", callback_data=f"accept_game_{game_id}")
    
    await bot.send_message(
        opponent[0],
        f"{STYLE['game']} ТЕБЕ ВЫЗОВ!\n\n"
        f"Пользователь @{callback.from_user.username} "
        f"приглашает тебя сыграть в {get_game_name(game_type)}!\n\n"
        f"Примешь вызов?",
        reply_markup=builder.as_markup()
    )
    
    await callback.answer("✅ Игрок приглашен!")

def get_game_name(game_type):
    games = {
        "whoami": "🎲 Кто я?",
        "number": "🎯 Угадай число",
        "love": "💕 Любовная викторина",
        "emoji": "🎨 Нарисуй эмоцию"
    }
    return games.get(game_type, "игру")

# ========== 7. 💬 ЧАТЫ ПО ИНТЕРЕСАМ ==========
@dp.message(F.text.in_([f"{STYLE['chat']} ЧАТЫ", "ЧАТЫ"]))
async def show_chats(message: Message):
    cursor.execute('SELECT id, name, interest, members_count FROM chat_rooms')
    chats = cursor.fetchall()
    
    text = f"""
{STYLE['divider']}
{STYLE['chat']} ЧАТЫ ПО ИНТЕРЕСАМ
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

@dp.callback_query(F.data.startswith("chat_"))
async def join_chat(callback: CallbackQuery):
    chat_id = int(callback.data.replace("chat_", ""))
    user_id = callback.from_user.id
    
    try:
        cursor.execute('''
            INSERT INTO chat_members (chat_id, user_id, joined_at)
            VALUES (?, ?, ?)
        ''', (chat_id, user_id, datetime.now().isoformat()))
        
        cursor.execute('UPDATE chat_rooms SET members_count = members_count + 1 WHERE id = ?', (chat_id,))
        conn.commit()
        
        await callback.answer(f"{STYLE['success']} Ты в чате!", show_alert=True)
        
        # Получаем ссылку на чат (тут можно создать реальный чат)
        await callback.message.answer(
            f"{STYLE['chat']} Ссылка на чат будет доступна в премиум версии!"
        )
        
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже в этом чате", show_alert=True)

# ========== 8. 🎂 ДНИ РОЖДЕНИЯ ==========
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
            f"{STYLE['cake']} День рождения сохранен!\n"
            f"Знак зодиака: {zodiac}\n"
            f"Возраст обновлен: {age}"
        )
        
    except:
        await message.answer("❌ Неверный формат. Используй: /setbirthday 01.01.1990")

def get_zodiac(date):
    day, month = date.day, date.month
    zodiacs = [
        ((1, 20), (2, 18), "♒ Водолей"), ((2, 19), (3, 20), "♓ Рыбы"),
        ((3, 21), (4, 19), "♈ Овен"), ((4, 20), (5, 20), "♉ Телец"),
        ((5, 21), (6, 20), "♊ Близнецы"), ((6, 21), (7, 22), "♋ Рак"),
        ((7, 23), (8, 22), "♌ Лев"), ((8, 23), (9, 22), "♍ Дева"),
        ((9, 23), (10, 22), "♎ Весы"), ((10, 23), (11, 21), "♏ Скорпион"),
        ((11, 22), (12, 21), "♐ Стрелец"), ((12, 22), (1, 19), "♑ Козерог")
    ]
    
    for (start_m, start_d), (end_m, end_d), sign in zodiacs:
        if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
            return sign
    return "♑ Козерог"

@dp.message(F.text.in_([f"{STYLE['cake']} ДНИ РОЖДЕНИЯ", "ДНИ РОЖДЕНИЯ"]))
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
{STYLE['cake']} ДНИ РОЖДЕНИЯ
{STYLE['divider']}

📅 СЕГОДНЯ:
"""
    
    if birthdays_today:
        for b in birthdays_today:
            text += f"🎂 {b[1]} - {b[3]}\n"
    else:
        text += "Сегодня именинников нет\n"
    
    # Ищем ближайшие дни рождения
    text += f"\n📅 БЛИЖАЙШИЕ:\n"
    
    cursor.execute('''
        SELECT u.first_name, b.birth_date, b.zodiac 
        FROM birthdays b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY 
            CASE 
                WHEN strftime('%m-%d', b.birth_date) >= ? THEN strftime('%m-%d', b.birth_date)
                ELSE strftime('%m-%d', b.birth_date) || '2000'
            END
        LIMIT 5
    ''', (today.strftime("%m-%d"),))
    
    upcoming = cursor.fetchall()
    for u in upcoming:
        text += f"📅 {u[0]} - {u[2]}\n"
    
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text)

# ========== 9. 📍 ГЕОЛОКАЦИЯ ==========
@dp.message(Command("sharelocation"))
async def share_location(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 ОТПРАВИТЬ ГЕОЛОКАЦИЮ", request_location=True)]],
        resize_keyboard=True
    )
    
    await message.answer(
        f"{STYLE['map']} Нажми кнопку, чтобы поделиться геолокацией\n"
        f"Это поможет находить людей рядом с тобой!",
        reply_markup=keyboard
    )

@dp.message(F.location)
async def handle_location(message: Message):
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    # Получаем город через обратное геокодирование
    city = "Неизвестно"  # Тут можно добавить API для определения города
    
    cursor.execute('''
        INSERT OR REPLACE INTO locations (user_id, latitude, longitude, city, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, lat, lon, city, datetime.now().isoformat()))
    conn.commit()
    
    await message.answer(
        f"{STYLE['success']} Геолокация сохранена!\n"
        f"Теперь тебя могут найти рядом",
        reply_markup=get_main_keyboard()
    )

# ========== 10. 🎨 СТИКЕРЫ ПИВЧИК ==========
@dp.message(F.text.in_([f"{STYLE['sticker']} СТИКЕРЫ", "СТИКЕРЫ"]))
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
{STYLE['sticker']} КОЛЛЕКЦИЯ СТИКЕРОВ
{STYLE['divider']}

"""
    
    builder = InlineKeyboardBuilder()
    for sticker in stickers:
        status = "✅" if sticker[5] else "❌"
        price_info = f"{sticker[3]} ⭐" if sticker[3] > 0 else "Бесплатно"
        premium_info = " 💎" if sticker[4] else ""
        
        text += f"{status} {sticker[2]} {sticker[1]}{premium_info} - {price_info}\n"
        
        if not sticker[5] and (not sticker[4] or user_id in ADMIN_IDS):
            builder.button(text=f"Купить {sticker[2]}", callback_data=f"buy_sticker_{sticker[0]}")
    
    builder.adjust(2)
    text += f"\n{STYLE['divider']}"
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_sticker_"))
async def buy_sticker(callback: CallbackQuery):
    user_id = callback.from_user.id
    sticker_id = int(callback.data.replace("buy_sticker_", ""))
    
    cursor.execute('SELECT price, is_premium FROM stickers WHERE id = ?', (sticker_id,))
    sticker = cursor.fetchone()
    
    if not sticker:
        await callback.answer("❌ Стикер не найден")
        return
    
    if sticker[1] == 1 and user_id not in ADMIN_IDS:
        cursor.execute('SELECT is_premium FROM users WHERE user_id = ?', (user_id,))
        is_premium = cursor.fetchone()
        if not is_premium or not is_premium[0]:
            await callback.answer("❌ Этот стикер только для премиум пользователей!", show_alert=True)
            return
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < sticker[0]:
        await callback.answer(f"❌ Недостаточно средств! Нужно {sticker[0]} ⭐", show_alert=True)
        return
    
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (sticker[0], user_id))
    cursor.execute('INSERT INTO user_stickers (user_id, sticker_id, obtained_at) VALUES (?, ?, ?)',
                  (user_id, sticker_id, datetime.now().isoformat()))
    conn.commit()
    
    await callback.answer(f"{STYLE['success']} Стикер куплен!", show_alert=True)
    await show_stickers(callback.message)

# ========== ОБНОВЛЕННАЯ ФУНКЦИЯ ЛАЙКОВ С УВЕДОМЛЕНИЯМИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer(f"{STYLE['error']} Нельзя лайкнуть себя!", show_alert=True)
        return
    
    # Проверка на бан
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (to_user,))
    banned = cursor.fetchone()
    if banned and banned[0] == 1:
        await callback.answer(f"{STYLE['error']} Этот пользователь заблокирован", show_alert=True)
        return
    
    cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,))
    user = cursor.fetchone()
    is_premium = user[0]
    likes_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"{STYLE['error']} Лимит лайков ({limit}) исчерпан!", show_alert=True)
        return
    
    try:
        cursor.execute('''
            INSERT INTO likes (from_user, to_user, created_at)
            VALUES (?, ?, ?)
        ''', (from_user, to_user, datetime.now().isoformat()))
        
        cursor.execute('UPDATE users SET likes_used = likes_used + 1 WHERE user_id = ?', (from_user,))
        cursor.execute('UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
        conn.commit()
        
        # Обновляем статистику
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute('''
            INSERT INTO bot_stats (date, likes_count) VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET likes_count = likes_count + 1
        ''', (today,))
        conn.commit()
        
        # Отправляем уведомление
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (from_user,))
        from_username = cursor.fetchone()[0]
        await send_like_notification(to_user, from_user, from_username)
        
        # Проверяем взаимность
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
            
            # Обновляем статистику взаимок
            cursor.execute('''
                INSERT INTO bot_stats (date, mutual_count) VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET mutual_count = mutual_count + 1
            ''', (today,))
            conn.commit()
            
            await callback.answer(f"{STYLE['mutual']} ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Получаем данные
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (to_user,))
            to_username = cursor.fetchone()[0]
            
            # Уведомление первому
            builder1 = InlineKeyboardBuilder()
            if to_username:
                builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
            builder1.button(text=f"{STYLE['view']} ПРОДОЛЖИТЬ", callback_data="next_profile")
            builder1.adjust(1)
            
            await bot.send_message(
                from_user,
                f"{STYLE['divider']}\n"
                f"{STYLE['mutual']} ВЗАИМНЫЙ ЛАЙК!\n"
                f"{STYLE['divider']}\n\n"
                f"Ты понравился {to_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder1.as_markup()
            )
            
            # Уведомление второму
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (from_user,))
            from_username = cursor.fetchone()[0]
            
            builder2 = InlineKeyboardBuilder()
            if from_username:
                builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
            builder2.button(text=f"{STYLE['view']} ПРОДОЛЖИТЬ", callback_data="next_profile")
            builder2.adjust(1)
            
            await bot.send_message(
                to_user,
                f"{STYLE['divider']}\n"
                f"{STYLE['mutual']} ВЗАИМНЫЙ ЛАЙК!\n"
                f"{STYLE['divider']}\n\n"
                f"Ты понравился {from_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder2.as_markup()
            )
            
        else:
            await callback.answer(f"{STYLE['like']} ЛАЙК ОТПРАВЛЕН!")
            
    except sqlite3.IntegrityError:
        await callback.answer(f"{STYLE['error']} Ты уже лайкал эту анкету", show_alert=True)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
{STYLE['header']}
{STYLE['beer']} ПИВЧИК 2.0 ЗАПУЩЕН!
{STYLE['beer']} АДМИН: {ADMIN_IDS[0]}
{STYLE['beer']} СТИЛЬ: ПИВЧИК
{STYLE['beer']} НОВЫЕ ФИЧИ: 10/10
{STYLE['beer']} СТАТУС: РАБОТАЕТ НА 100%
{STYLE['beer']} ФИЧИ:
{STYLE['beer']} 1. 🔔 Уведомления о лайках
{STYLE['beer']} 2. 🎁 Реферальная система
{STYLE['beer']} 3. 🌍 Фильтр по городам
{STYLE['beer']} 4. 🔥 Топ-чарт
{STYLE['beer']} 5. 📸 Несколько фото
{STYLE['beer']} 6. 🎮 Игры
{STYLE['beer']} 7. 💬 Чаты по интересам
{STYLE['beer']} 8. 🎂 Дни рождения
{STYLE['beer']} 9. 📍 Геолокация
{STYLE['beer']} 10. 🎨 Стикеры
{STYLE['header']}
""")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
