import logging
import sqlite3
import asyncio
import json
import random
from datetime import datetime, timedelta
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
from aiogram.types import FSInputFile

# ========== СТИЛЬ ДАЙВИНЧИК + ПИВЧИК ==========
STYLE = {
    "name": " ПИВЧИК",
    "header": "🎨══════ ПИВЧИК ══════🎨",
    "divider": "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰",
    "art": "🎭",
    "like": "💋",
    "mutual": "💕",
    "profile": "🖼️",
    "view": "👁️",
    "premium": "👑",
    "stats": "📈",
    "settings": "⚙️",
    "help": "❓",
    "balance": "💎",
    "back": "◀️",
    "next": "▶️",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "crown": "👑",
    "fire": "🔥",
    "gift": "🎁",
    "game": "🎲",
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
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("daivinchik.db")
        self.cursor = self.conn.cursor()
        self.create_tables()
        print("🎨 База данных ДАЙВИНЧИК подключена")
    
    def create_tables(self):
        # Пользователи с арт-статистикой
        self.cursor.execute('''
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
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                referral_earnings INTEGER DEFAULT 0,
                city TEXT,
                last_active TEXT,
                art_style TEXT DEFAULT 'Классика',
                masterpieces_created INTEGER DEFAULT 0
            )
        ''')
        
        # Анкеты как произведения искусства
        self.cursor.execute('''
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
                art_style TEXT,
                masterpiece TEXT
            )
        ''')
        
        # Лайки (музы)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS muses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                created_at TEXT,
                is_mutual INTEGER DEFAULT 0,
                UNIQUE(from_user, to_user)
            )
        ''')
        
        # Просмотры (вдохновение)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspiration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                viewed_user_id INTEGER,
                viewed_at TEXT,
                UNIQUE(user_id, viewed_user_id)
            )
        ''')
        
        # Рефералы (ученики)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS apprentices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER,
                apprentice_id INTEGER UNIQUE,
                created_at TEXT
            )
        ''')
        
        # Дни рождения (даты создания шедевров)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS masterpieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                birth_date TEXT,
                zodiac TEXT
            )
        ''')
        
        self.conn.commit()
    
    # Методы для пользователей
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def create_user(self, user_id, username, first_name):
        referral_code = f"DAV{user_id}{random.randint(1000, 9999)}"
        self.cursor.execute('''
            INSERT INTO users (user_id, username, first_name, joined_date, last_active, referral_code, balance)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat(), referral_code))
        self.conn.commit()
    
    def update_last_active(self, user_id):
        self.cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                          (datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def add_balance(self, user_id, amount):
        self.cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()
    
    # Методы для анкет
    def get_profile(self, user_id):
        self.cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = 1', (user_id,))
        return self.cursor.fetchone()
    
    def create_profile(self, user_id, name, age, gender, city, about, photo):
        photos = json.dumps([photo])
        art_styles = ["Классика", "Ренессанс", "Барокко", "Модерн", "Абстракция"]
        art_style = random.choice(art_styles)
        
        self.cursor.execute('''
            INSERT INTO profiles (user_id, name, age, gender, city, about, photos, created_at, updated_at, art_style)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, age, gender, city, about, photos, datetime.now().isoformat(), datetime.now().isoformat(), art_style))
        
        self.cursor.execute('UPDATE users SET art_style = ?, masterpieces_created = masterpieces_created + 1 WHERE user_id = ?', 
                          (art_style, user_id))
        self.conn.commit()
        return art_style
    
    def update_profile(self, user_id, field, value):
        self.cursor.execute(f'UPDATE profiles SET {field} = ?, updated_at = ? WHERE user_id = ?', 
                          (value, datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def add_photo(self, user_id, photo_id):
        profile = self.get_profile(user_id)
        if profile:
            photos = json.loads(profile[7]) if profile[7] else []
            if len(photos) < 5:
                photos.append(photo_id)
                self.cursor.execute('UPDATE profiles SET photos = ?, updated_at = ? WHERE user_id = ?',
                                  (json.dumps(photos), datetime.now().isoformat(), user_id))
                self.conn.commit()
                return True
        return False
    
    def delete_profile(self, user_id):
        self.cursor.execute('UPDATE profiles SET is_active = 0 WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM muses WHERE from_user = ? OR to_user = ?', (user_id, user_id))
        self.cursor.execute('DELETE FROM inspiration WHERE user_id = ? OR viewed_user_id = ?', (user_id, user_id))
        self.conn.commit()
    
    # Методы для лайков (муз)
    def add_muse(self, from_user, to_user):
        try:
            self.cursor.execute('''
                INSERT INTO muses (from_user, to_user, created_at)
                VALUES (?, ?, ?)
            ''', (from_user, to_user, datetime.now().isoformat()))
            
            self.cursor.execute('UPDATE users SET likes_used = likes_used + 1 WHERE user_id = ?', (from_user,))
            self.cursor.execute('UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
            self.conn.commit()
            
            self.cursor.execute('SELECT 1 FROM muses WHERE from_user = ? AND to_user = ?', (to_user, from_user))
            if self.cursor.fetchone():
                self.cursor.execute('''
                    UPDATE muses SET is_mutual = 1 
                    WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                ''', (from_user, to_user, to_user, from_user))
                self.conn.commit()
                return True
            return False
        except sqlite3.IntegrityError:
            return None
    
    # Методы для рефералов (учеников)
    def process_apprentice(self, code, new_user_id):
        self.cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (code,))
        master = self.cursor.fetchone()
        if master and master[0] != new_user_id:
            self.cursor.execute('''
                INSERT INTO apprentices (master_id, apprentice_id, created_at)
                VALUES (?, ?, ?)
            ''', (master[0], new_user_id, datetime.now().isoformat()))
            
            self.cursor.execute('''
                UPDATE users SET 
                    referral_count = referral_count + 1,
                    balance = balance + 50,
                    referral_earnings = referral_earnings + 50
                WHERE user_id = ?
            ''', (master[0],))
            
            self.cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (master[0], new_user_id))
            self.conn.commit()
            return master[0]
        return None
    
    # Методы для поиска
    def get_random_profile(self, user_id):
        self.cursor.execute('''
            SELECT p.*, u.username FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id != ? 
            AND p.is_active = 1
            AND u.is_banned = 0
            AND p.user_id NOT IN (
                SELECT viewed_user_id FROM inspiration WHERE user_id = ?
            )
            ORDER BY RANDOM()
            LIMIT 1
        ''', (user_id, user_id))
        return self.cursor.fetchone()
    
    def get_top_likes(self, limit=10):
        self.cursor.execute('''
            SELECT p.name, p.likes_count, p.photos, u.user_id, p.art_style
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.likes_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_top_views(self, limit=10):
        self.cursor.execute('''
            SELECT p.name, p.views_count, p.photos, u.user_id, p.art_style
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.views_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_nearby(self, city, user_id):
        self.cursor.execute('''
            SELECT p.name, p.age, p.gender, p.photos, p.art_style
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE u.city = ? AND p.user_id != ? AND p.is_active = 1
            ORDER BY RANDOM()
            LIMIT 5
        ''', (city, user_id))
        return self.cursor.fetchall()
    
    # Методы для дней рождения (шедевров)
    def set_masterpiece(self, user_id, birth_date, zodiac):
        self.cursor.execute('''
            INSERT OR REPLACE INTO masterpieces (user_id, birth_date, zodiac)
            VALUES (?, ?, ?)
        ''', (user_id, birth_date, zodiac))
        self.conn.commit()
    
    def get_today_masterpieces(self):
        today = datetime.now().strftime("%d.%m")
        self.cursor.execute('''
            SELECT u.first_name, m.zodiac
            FROM masterpieces m
            JOIN users u ON m.user_id = u.user_id
            WHERE substr(m.birth_date, 1, 5) = ?
        ''', (today,))
        return self.cursor.fetchall()
    
    def get_upcoming_masterpieces(self, limit=5):
        self.cursor.execute('''
            SELECT u.first_name, m.birth_date, m.zodiac
            FROM masterpieces m
            JOIN users u ON m.user_id = u.user_id
            ORDER BY 
                CASE 
                    WHEN substr(m.birth_date, 6) >= strftime('%m-%d', 'now') 
                    THEN substr(m.birth_date, 6)
                    ELSE '99-99'
                END
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_zodiac(self, day, month):
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

db = Database()

# ========== FSM СОСТОЯНИЯ ==========
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

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ В СТИЛЕ ДАЙВИНЧИК ==========
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🖼️ МОЙ ШЕДЕВР"), KeyboardButton(text="👁️ ВДОХНОВЕНИЕ")],
        [KeyboardButton(text="👑 ПРЕМИУМ"), KeyboardButton(text="📈 МОЯ ГАЛЕРЕЯ")],
        [KeyboardButton(text="🔥 ТОП ШЕДЕВРОВ"), KeyboardButton(text="🎁 УЧЕНИКИ")],
        [KeyboardButton(text="🎲 ИГРЫ МАСТЕРОВ"), KeyboardButton(text="💬 АРТ-ЧАТЫ")],
        [KeyboardButton(text="🎂 ДНИ ШЕДЕВРОВ"), KeyboardButton(text="📍 РЯДОМ")],
        [KeyboardButton(text="🎨 СТИКЕРЫ"), KeyboardButton(text="⚙️ МАСТЕРСКАЯ")],
        [KeyboardButton(text="💎 МОИ СОКРОВИЩА"), KeyboardButton(text="❓ ПОМОЩЬ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    kb = [[KeyboardButton(text="◀️ НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    kb = [
        [KeyboardButton(text="МУЖСКАЯ МУЗА"), KeyboardButton(text="ЖЕНСКАЯ МУЗА")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_art_style_keyboard():
    kb = [
        [KeyboardButton(text="🎨 Классика"), KeyboardButton(text="🏛️ Ренессанс")],
        [KeyboardButton(text="👑 Барокко"), KeyboardButton(text="🎭 Модерн")],
        [KeyboardButton(text="🌀 Абстракция")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
        
        args = message.text.split()
        if len(args) > 1:
            master_id = db.process_apprentice(args[1], user_id)
            if master_id:
                await bot.send_message(
                    master_id,
                    f"🎁 НОВЫЙ УЧЕНИК!\n\n"
                    f"Художник @{message.from_user.username} присоединился по твоей ссылке!\n"
                    f"Начислено 50 💎 на баланс!"
                )
    
    db.update_last_active(user_id)
    
    welcome_text = f"""
🎨══════ ДАЙВИНЧИК ══════🎨

🖼️ {message.from_user.first_name}, добро пожаловать в галерею искусств!

Здесь каждый создает свой шедевр и находит свою музу.

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

👇 СОЗДАЙ СВОЙ ШЕДЕВР:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== 🖼️ МОЙ ШЕДЕВР (МОЯ АНКЕТА) ==========
@dp.message(F.text.in_(["🖼️ МОЙ ШЕДЕВР", "МОЙ ШЕДЕВР"]))
async def my_profile(message: Message):
    user_id = message.from_user.id
    profile = db.get_profile(user_id)
    
    if not profile:
        await message.answer(
            f"❌ У тебя ещё нет шедевра!\n"
            f"Нажми /create чтобы создать"
        )
        return
    
    views = db.cursor.execute('SELECT COUNT(*) FROM inspiration WHERE viewed_user_id = ?', (user_id,)).fetchone()[0]
    likes = db.cursor.execute('SELECT COUNT(*) FROM muses WHERE to_user = ?', (user_id,)).fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM muses WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]
    
    user = db.get_user(user_id)
    is_premium = user[3] if user else 0
    premium_badge = f" 👑" if is_premium else ""
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🖼️ ТВОЙ ШЕДЕВР{premium_badge}
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

👤 Имя: {profile[2]}
📅 Возраст: {profile[3]}
⚥ Пол: {profile[4]}
🏙 Город: {profile[5]}
🎨 Стиль: {profile[13] if len(profile) > 13 else 'Классика'}

📝 Описание:
{profile[6]}

📸 Шедевров: {len(photos)}

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
📈 ПОПУЛЯРНОСТЬ:
👁️ Вдохновил: {views}
💋 Муз: {likes}
💕 Взаимных: {mutual}
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ РЕДАКТИРОВАТЬ", callback_data="edit_menu")
    builder.button(text="📸 ДОБАВИТЬ ШЕДЕВР", callback_data="add_photo")
    builder.button(text="🗑 УДАЛИТЬ", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if main_photo:
        await message.answer_photo(
            photo=main_photo,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== 👁️ ВДОХНОВЕНИЕ (СМОТРЕТЬ) ==========
@dp.message(F.text.in_(["👁️ ВДОХНОВЕНИЕ", "ВДОХНОВЕНИЕ"]))
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    if not db.get_profile(user_id):
        await message.answer("❌ Сначала создай свой шедевр через /create")
        return
    
    user = db.get_user(user_id)
    is_premium = user[3] if user else 0
    views_used = user[5] if user else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(f"❌ Лимит вдохновения исчерпан ({limit})\nКупи 👑 ПРЕМИУМ")
        return
    
    profile = db.get_random_profile(user_id)
    
    if not profile:
        await message.answer("🎨 Ты вдохновился всеми шедеврами! Заходи позже")
        return
    
    db.cursor.execute('''
        INSERT INTO inspiration (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    db.cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    db.cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    db.conn.commit()
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    gender_emoji = "👨" if profile[4] == "Мужской" else "👩"
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
{gender_emoji} {profile[2]}, {profile[3]}
🏙 {profile[5]}
🎨 Стиль: {profile[13] if len(profile) > 13 else 'Классика'}

📝 Описание:
{profile[6]}

💋 Муз: {profile[10]} | 👁️ Вдохновил: {profile[9]}
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💋 СТАТЬ МУЗОЙ", callback_data=f"like_{profile[1]}")
    builder.button(text="▶️ ДАЛЬШЕ", callback_data="next_profile")
    builder.button(text="⚠️ ПОЖАЛОВАТЬСЯ", callback_data=f"complaint_{profile[1]}")
    if profile[-1]:
        builder.button(text="📱 НАПИСАТЬ", url=f"https://t.me/{profile[-1]}")
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

# ========== 💋 ЛАЙКИ (МУЗЫ) ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer("❌ Нельзя быть своей музой!", show_alert=True)
        return
    
    user = db.get_user(from_user)
    is_premium = user[3] if user else 0
    likes_used = user[4] if user else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит муз ({limit}) исчерпан!", show_alert=True)
        return
    
    result = db.add_muse(from_user, to_user)
    
    if result is None:
        await callback.answer("❌ Ты уже был музой для этого шедевра", show_alert=True)
    elif result is True:
        await callback.answer("💕 ВЗАИМНАЯ МУЗА!", show_alert=True)
        
        to_profile = db.get_profile(to_user)
        to_name = to_profile[2] if to_profile else "Художник"
        to_user_data = db.get_user(to_user)
        to_username = to_user_data[1] if to_user_data else None
        
        from_profile = db.get_profile(from_user)
        from_name = from_profile[2] if from_profile else "Художник"
        
        builder1 = InlineKeyboardBuilder()
        if to_username:
            builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
        builder1.button(text="👁️ ПРОДОЛЖИТЬ", callback_data="next_profile")
        
        await bot.send_message(
            from_user,
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"💕 ВЗАИМНАЯ МУЗА!\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
            f"Ты вдохновил {to_name}!\n\n"
            f"Теперь вы можете создать совместный шедевр!",
            reply_markup=builder1.as_markup()
        )
        
        from_user_data = db.get_user(from_user)
        from_username = from_user_data[1] if from_user_data else None
        
        builder2 = InlineKeyboardBuilder()
        if from_username:
            builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
        builder2.button(text="👁️ ПРОДОЛЖИТЬ", callback_data="next_profile")
        
        await bot.send_message(
            to_user,
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"💕 ВЗАИМНАЯ МУЗА!\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
            f"Ты вдохновил {from_name}!\n\n"
            f"Теперь вы можете создать совместный шедевр!",
            reply_markup=builder2.as_markup()
        )
    else:
        await callback.answer("💋 ТЫ СТАЛ МУЗОЙ!")

# ========== 👑 ПРЕМИУМ ==========
@dp.message(F.text.in_(["👑 ПРЕМИУМ", "ПРЕМИУМ"]))
async def show_premium(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
👑 ПРЕМИУМ ДАЙВИНЧИК
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

📊 ЛИМИТЫ ВДОХНОВЕНИЯ:
• Обычный художник: {FREE_LIMIT} 👁️/💋
• Мастер с премиум: {PREMIUM_LIMIT} 👁️/💋

✨ БОНУСЫ ПРЕМИУМ:
• 👑 Корона в профиле
• 🎨 Эксклюзивные стили
• 🔥 Показ в топе галереи
• 💎 Особые стикеры

💰 ЦЕНА:
• 50 💎 = 1 день
• 250 💎 = 7 дней
• 1000 💎 = 30 дней
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 50 (1 день)", callback_data="buy_50")
    builder.button(text="💎 250 (7 дней)", callback_data="buy_250")
    builder.button(text="💎 1000 (30 дней)", callback_data="buy_1000")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 📈 МОЯ ГАЛЕРЕЯ (СТАТИСТИКА) ==========
@dp.message(F.text.in_(["📈 МОЯ ГАЛЕРЕЯ", "МОЯ ГАЛЕРЕЯ"]))
async def show_stats(message: Message):
    user_id = message.from_user.id
    
    viewed = db.cursor.execute('SELECT COUNT(*) FROM inspiration WHERE user_id = ?', (user_id,)).fetchone()[0]
    viewed_me = db.cursor.execute('SELECT COUNT(*) FROM inspiration WHERE viewed_user_id = ?', (user_id,)).fetchone()[0]
    likes_given = db.cursor.execute('SELECT COUNT(*) FROM muses WHERE from_user = ?', (user_id,)).fetchone()[0]
    likes_received = db.cursor.execute('SELECT COUNT(*) FROM muses WHERE to_user = ?', (user_id,)).fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM muses WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]
    
    user = db.get_user(user_id)
    is_premium = user[3] if user else 0
    views_used = user[5] if user else 0
    likes_used = user[4] if user else 0
    masterpieces = user[13] if user and len(user) > 13 else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
📈 ТВОЯ ГАЛЕРЕЯ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

🖼️ Шедевров создано: {masterpieces}
👁️ Ты вдохновился: {viewed}
👁️ Тобой вдохновились: {viewed_me}
💋 Ты стал музой для: {likes_given}
💋 Твоими музами стали: {likes_received}
💕 Взаимных муз: {mutual}

📈 ОСТАЛОСЬ ВДОХНОВЕНИЯ:
• 👁️ {limit - views_used}
• 💋 {limit - likes_used}
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    await message.answer(text)

# ========== 🔥 ТОП ШЕДЕВРОВ ==========
@dp.message(F.text.in_(["🔥 ТОП ШЕДЕВРОВ", "ТОП ШЕДЕВРОВ"]))
async def show_top(message: Message):
    top_likes = db.get_top_likes(5)
    top_views = db.get_top_views(5)
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🔥 ТОП ШЕДЕВРОВ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

💋 ТОП ПО МУЗАМ:
"""
    
    for i, profile in enumerate(top_likes, 1):
        text += f"{i}. {profile[0]} ({profile[4]}) - {profile[1]} 💋\n"
    
    text += f"\n👁️ ТОП ПО ВДОХНОВЕНИЮ:\n"
    
    for i, profile in enumerate(top_views, 1):
        text += f"{i}. {profile[0]} ({profile[4]}) - {profile[1]} 👁️\n"
    
    text += f"\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    
    await message.answer(text)

# ========== 🎁 УЧЕНИКИ (РЕФЕРАЛЫ) ==========
@dp.message(F.text.in_(["🎁 УЧЕНИКИ", "УЧЕНИКИ"]))
async def show_referrals(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        return
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user[8]}"  # referral_code
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🎁 ТВОИ УЧЕНИКИ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

📊 СТАТИСТИКА:
• Учеников: {user[9]} чел.
• Заработано: {user[10]} 💎

💰 НАГРАДЫ:
• За каждого ученика: 50 💎
• За 10 учеников: +1 день 👑
• За 50 учеников: +7 дней 👑

🔗 ТВОЯ ССЫЛКА:
{referral_link}

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    await message.answer(text)

# ========== 🎲 ИГРЫ МАСТЕРОВ ==========
@dp.message(F.text.in_(["🎲 ИГРЫ МАСТЕРОВ", "ИГРЫ МАСТЕРОВ"]))
async def show_games(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🎲 ИГРЫ МАСТЕРОВ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

🎭 УГАДАЙ СТИЛЬ
Определи направление искусства

🎨 НАРИСУЙ ЭМОЦИЮ
Угадай по смайликам

🖼️ СОЗДАЙ ШЕДЕВР
Собери картину по частям

💕 ЛЮБОВНАЯ ГАЛЕРЕЯ
Вопросы о совместимости

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🎭 УГАДАЙ СТИЛЬ", callback_data="game_style")
    builder.button(text="🎨 НАРИСУЙ ЭМОЦИЮ", callback_data="game_emoji")
    builder.button(text="🖼️ СОЗДАЙ ШЕДЕВР", callback_data="game_masterpiece")
    builder.button(text="💕 ЛЮБОВНАЯ ГАЛЕРЕЯ", callback_data="game_love")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 💬 АРТ-ЧАТЫ ==========
@dp.message(F.text.in_(["💬 АРТ-ЧАТЫ", "АРТ-ЧАТЫ"]))
async def show_chats(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
💬 АРТ-ЧАТЫ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

🎨 КЛАССИКА
🏛️ РЕНЕССАНС
👑 БАРОККО
🎭 МОДЕРН
🌀 АБСТРАКЦИЯ
🖼️ СОВРЕМЕННОЕ
📸 ФОТОГРАФИЯ
🎭 ТЕАТР

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 КЛАССИКА", callback_data="chat_classic")
    builder.button(text="🏛️ РЕНЕССАНС", callback_data="chat_renaissance")
    builder.button(text="👑 БАРОККО", callback_data="chat_baroque")
    builder.button(text="🎭 МОДЕРН", callback_data="chat_modern")
    builder.button(text="🌀 АБСТРАКЦИЯ", callback_data="chat_abstract")
    builder.button(text="🖼️ СОВРЕМЕННОЕ", callback_data="chat_contemporary")
    builder.button(text="📸 ФОТОГРАФИЯ", callback_data="chat_photo")
    builder.button(text="🎭 ТЕАТР", callback_data="chat_theater")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 🎂 ДНИ ШЕДЕВРОВ (ДНИ РОЖДЕНИЯ) ==========
@dp.message(F.text.in_(["🎂 ДНИ ШЕДЕВРОВ", "ДНИ ШЕДЕВРОВ"]))
async def show_birthdays(message: Message):
    today = db.get_today_masterpieces()
    upcoming = db.get_upcoming_masterpieces()
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🎂 ДНИ ШЕДЕВРОВ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

📅 СЕГОДНЯ:
"""
    
    if today:
        for name, zodiac in today:
            text += f"🎨 {name} - {zodiac}\n"
    else:
        text += "Сегодня нет именинников\n"
    
    text += f"\n📅 БЛИЖАЙШИЕ:\n"
    
    for name, date, zodiac in upcoming:
        text += f"📅 {name} - {zodiac} ({date[:5]})\n"
    
    text += f"\nЧтобы добавить свой день:\n/setbirthday ДД.ММ.ГГГГ"
    text += f"\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    
    await message.answer(text)

@dp.message(Command("setbirthday"))
async def set_birthday(message: Message):
    try:
        date_str = message.text.replace("/setbirthday", "").strip()
        birth_date = datetime.strptime(date_str, "%d.%m.%Y")
        
        zodiac = db.get_zodiac(birth_date.day, birth_date.month)
        db.set_masterpiece(message.from_user.id, date_str, zodiac)
        
        age = (datetime.now() - birth_date).days // 365
        if db.get_profile(message.from_user.id):
            db.update_profile(message.from_user.id, "age", age)
        
        await message.answer(
            f"✅ Дата шедевра сохранена!\n"
            f"Знак зодиака: {zodiac}\n"
            f"Возраст: {age}"
        )
    except:
        await message.answer("❌ Неверный формат. Используй: /setbirthday 01.01.1990")

# ========== 📍 РЯДОМ ==========
@dp.message(F.text.in_(["📍 РЯДОМ", "РЯДОМ"]))
async def find_nearby(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user[11]:  # city
        await message.answer(
            f"⚠️ Укажи свой город!\n"
            f"Используй /setcity НазваниеГорода"
        )
        return
    
    nearby = db.get_nearby(user[11], user_id)
    
    if not nearby:
        await message.answer(
            f"❌ В твоем городе пока нет художников!\n"
            f"Пригласи друзей через 🎁 УЧЕНИКИ"
        )
        return
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
📍 ХУДОЖНИКИ РЯДОМ ({user[11]})
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

"""
    
    for name, age, gender, photos, style in nearby:
        gender_emoji = "👨" if gender == "Мужской" else "👩"
        text += f"{gender_emoji} {name}, {age} - {style}\n"
    
    text += f"\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    
    await message.answer(text)

@dp.message(Command("setcity"))
async def set_city(message: Message):
    city = message.text.replace("/setcity", "").strip()
    if not city:
        await message.answer("❌ Напиши: /setcity НазваниеГорода")
        return
    
    db.cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (city, message.from_user.id))
    db.conn.commit()
    
    await message.answer(f"✅ Город {city} сохранен!")

# ========== 🎨 СТИКЕРЫ ==========
@dp.message(F.text.in_(["🎨 СТИКЕРЫ", "СТИКЕРЫ"]))
async def show_stickers(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
🎨 КОЛЛЕКЦИЯ СТИКЕРОВ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

🎭 МАСКА - 0 💎
🎨 ПАЛИТРА - 10 💎
👑 КОРОНА - 100 💎 (👑)
🖼️ КАРТИНА - 20 💎
🎁 ПОДАРОК - 0 💎
✨ КИСТЬ - 50 💎
🌟 ЗВЕЗДА - 30 💎
💫 ВДОХНОВЕНИЕ - 15 💎

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🎭 МАСКА", callback_data="buy_sticker_1")
    builder.button(text="🎨 ПАЛИТРА", callback_data="buy_sticker_2")
    builder.button(text="👑 КОРОНА", callback_data="buy_sticker_3")
    builder.button(text="🖼️ КАРТИНА", callback_data="buy_sticker_4")
    builder.button(text="🎁 ПОДАРОК", callback_data="buy_sticker_5")
    builder.button(text="✨ КИСТЬ", callback_data="buy_sticker_6")
    builder.button(text="🌟 ЗВЕЗДА", callback_data="buy_sticker_7")
    builder.button(text="💫 ВДОХНОВЕНИЕ", callback_data="buy_sticker_8")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== ⚙️ МАСТЕРСКАЯ (НАСТРОЙКИ) ==========
@dp.message(F.text.in_(["⚙️ МАСТЕРСКАЯ", "МАСТЕРСКАЯ"]))
async def show_settings(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
⚙️ МАСТЕРСКАЯ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

/setcity Город - указать город
/setbirthday ДД.ММ.ГГГГ - день шедевра
/create - создать шедевр

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    await message.answer(text)

# ========== 💎 МОИ СОКРОВИЩА (БАЛАНС) ==========
@dp.message(F.text.in_(["💎 МОИ СОКРОВИЩА", "МОИ СОКРОВИЩА"]))
async def show_balance(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    balance = user[7] if user else 0
    
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
💎 ТВОИ СОКРОВИЩА
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

У тебя: {balance} 💎

Пополнить через 👑 ПРЕМИУМ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    await message.answer(text)

# ========== ❓ ПОМОЩЬ ==========
@dp.message(F.text.in_(["❓ ПОМОЩЬ", "ПОМОЩЬ"]))
async def show_help(message: Message):
    text = f"""
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
❓ ПОМОЩЬ
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

📝 КОМАНДЫ:
/create - создать шедевр
/setcity - указать город
/setbirthday - день шедевра

🖼️ МОЙ ШЕДЕВР - просмотр/редактирование
👁️ ВДОХНОВЕНИЕ - смотреть анкеты
💋 СТАТЬ МУЗОЙ - поставить лайк
💕 ВЗАИМНАЯ МУЗА - можно писать

🔥 ТОП ШЕДЕВРОВ - самые популярные
🎁 УЧЕНИКИ - приглашай друзей
🎲 ИГРЫ МАСТЕРОВ - игры для знакомств
💬 АРТ-ЧАТЫ - общение по интересам

⚠️ ПРАВИЛА:
• Только настоящие шедевры
• Без плагиата
• Возраст 18+

👨‍🎨 По вопросам: @admin
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
"""
    
    await message.answer(text)

# ========== ◀️ НАЗАД ==========
@dp.message(F.text.in_(["◀️ НАЗАД", "НАЗАД"]))
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# ========== СОЗДАНИЕ ШЕДЕВРА (АНКЕТЫ) ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.get_profile(user_id):
        await message.answer(
            f"❌ У тебя уже есть шедевр!\n"
            f"Если хочешь создать новый, удали старый."
        )
        return
    
    await message.answer(
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"🎨 СОЗДАНИЕ ШЕДЕВРА\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        f"Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя")
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
    if message.text.upper() not in ["МУЖСКАЯ МУЗА", "ЖЕНСКАЯ МУЗА", "МУЖСКОЙ", "ЖЕНСКИЙ"]:
        await message.answer("❌ Используй кнопки")
        return
    
    gender = "Мужской" if "МУЖСК" in message.text.upper() else "Женский"
    await state.update_data(gender=gender)
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное название города")
        return
    
    await state.update_data(city=message.text)
    await message.answer(
        f"📝 Опиши свой шедевр\n"
        f"(чем увлекаешься, что ищешь)\n\n"
        f"⚠️ Без ссылок!",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer("❌ Ссылки запрещены!")
        return
    
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь фото своего шедевра",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    art_style = db.create_profile(
        message.from_user.id,
        data['name'],
        data['age'],
        data['gender'],
        data['city'],
        data['about'],
        photo_id
    )
    
    await state.clear()
    await message.answer(
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"✅ ШЕДЕВР СОЗДАН!\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        f"Твой стиль: {art_style}\n\n"
        f"Теперь ищи вдохновение 👁️",
        reply_markup=get_main_keyboard()
    )

# ========== РЕДАКТИРОВАНИЕ ==========
@dp.callback_query(F.data == "edit_menu")
async def edit_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 ИМЯ", callback_data="edit_name")
    builder.button(text="📅 ВОЗРАСТ", callback_data="edit_age")
    builder.button(text="⚥ ПОЛ", callback_data="edit_gender")
    builder.button(text="🏙 ГОРОД", callback_data="edit_city")
    builder.button(text="📝 ОПИСАНИЕ", callback_data="edit_about")
    builder.button(text="◀️ НАЗАД", callback_data="back_to_profile")
    builder.adjust(2, 2, 1, 1)
    
    await callback.message.edit_caption(
        caption=f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n✏️ РЕДАКТИРОВАНИЕ\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\nЧто хочешь изменить?",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery):
    await callback.message.delete()
    await my_profile(callback.message)

@dp.callback_query(F.data.startswith("edit_"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    
    await state.update_data(edit_field=field)
    await callback.message.delete()
    
    if field == "gender":
        await callback.message.answer(
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"✏️ ИЗМЕНЕНИЕ ПОЛА\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
            f"Выбери новый пол:",
            reply_markup=get_gender_keyboard()
        )
    else:
        field_names = {"name": "ИМЯ", "age": "ВОЗРАСТ", "city": "ГОРОД", "about": "ОПИСАНИЕ"}
        await callback.message.answer(
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"✏️ ИЗМЕНЕНИЕ {field_names.get(field, '')}\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
            f"Введи новое значение:",
            reply_markup=get_back_keyboard()
        )
    
    await state.set_state(EditProfileStates.value)

@dp.message(EditProfileStates.value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    user_id = message.from_user.id
    
    if field == "name":
        if len(message.text) > 50:
            await message.answer("❌ Слишком длинное имя")
            return
        db.update_profile(user_id, "name", message.text)
        await message.answer("✅ Имя обновлено!")
        
    elif field == "age":
        try:
            age = int(message.text)
            if age < MIN_AGE or age > MAX_AGE:
                raise ValueError
            db.update_profile(user_id, "age", age)
            await message.answer("✅ Возраст обновлен!")
        except:
            await message.answer(f"❌ Введи число от {MIN_AGE} до {MAX_AGE}")
            return
            
    elif field == "gender":
        if message.text.upper() not in ["МУЖСКАЯ МУЗА", "ЖЕНСКАЯ МУЗА", "МУЖСКОЙ", "ЖЕНСКИЙ"]:
            await message.answer("❌ Используй кнопки")
            return
        gender = "Мужской" if "МУЖСК" in message.text.upper() else "Женский"
        db.update_profile(user_id, "gender", gender)
        await message.answer("✅ Пол обновлен!")
        
    elif field == "city":
        if len(message.text) > 50:
            await message.answer("❌ Слишком длинное название города")
            return
        db.update_profile(user_id, "city", message.text)
        await message.answer("✅ Город обновлен!")
        
    elif field == "about":
        if len(message.text) > 500:
            await message.answer("❌ Слишком длинное описание")
            return
        db.update_profile(user_id, "about", message.text)
        await message.answer("✅ Описание обновлено!")
    
    await state.clear()
    await message.answer("🖼️ Возвращаемся в галерею...", reply_markup=get_main_keyboard())
    await my_profile(message)

@dp.callback_query(F.data == "add_photo")
async def add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"📸 ДОБАВЛЕНИЕ ШЕДЕВРА\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        f"Отправь фото (можно добавить до 5 шт)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photos)

@dp.message(ProfileStates.photos, F.photo)
async def process_add_photo(message: Message, state: FSMContext):
    result = db.add_photo(message.from_user.id, message.photo[-1].file_id)
    
    if result:
        await message.answer(f"✅ Шедевр добавлен!")
    else:
        await message.answer(f"❌ Ошибка (макс. 5 шедевров)")
        await state.clear()
        await my_profile(message)

# ========== УДАЛЕНИЕ ==========
@dp.callback_query(F.data == "delete_profile")
async def delete_profile_confirm(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ДА, УДАЛИТЬ", callback_data="confirm_delete")
    builder.button(text="◀️ ОТМЕНА", callback_data="back_to_profile")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption=f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                f"⚠️ УДАЛЕНИЕ ШЕДЕВРА\n"
                f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
                f"Ты уверен? Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_delete")
async def delete_profile(callback: CallbackQuery):
    db.delete_profile(callback.from_user.id)
    
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Шедевр удален!\n"
        f"Чтобы создать новый, нажми /create",
        reply_markup=get_main_keyboard()
    )

# ========== CALLBACKS ДЛЯ ИГР ==========
@dp.callback_query(F.data.startswith("game_"))
async def game_callback(callback: CallbackQuery):
    game = callback.data.replace("game_", "")
    
    games = {
        "style": "🎭 Угадай стиль",
        "emoji": "🎨 Нарисуй эмоцию",
        "masterpiece": "🖼️ Создай шедевр",
        "love": "💕 Любовная галерея"
    }
    
    await callback.message.answer(f"{games.get(game, '🎲')} скоро будет доступна!")
    await callback.answer()

# ========== CALLBACKS ДЛЯ ЧАТОВ ==========
@dp.callback_query(F.data.startswith("chat_"))
async def chat_callback(callback: CallbackQuery):
    chat = callback.data.replace("chat_", "")
    
    chats = {
        "classic": "🎨 Классика",
        "renaissance": "🏛️ Ренессанс",
        "baroque": "👑 Барокко",
        "modern": "🎭 Модерн",
        "abstract": "🌀 Абстракция",
        "contemporary": "🖼️ Современное",
        "photo": "📸 Фотография",
        "theater": "🎭 Театр"
    }
    
    await callback.message.answer(
        f"💬 Чат '{chats.get(chat, 'Арт-чат')}' скоро будет доступен!\n"
        f"Следи за обновлениями!"
    )
    await callback.answer()

# ========== CALLBACKS ДЛЯ СТИКЕРОВ ==========
@dp.callback_query(F.data.startswith("buy_sticker_"))
async def buy_sticker(callback: CallbackQuery):
    sticker_id = int(callback.data.replace("buy_sticker_", ""))
    prices = [0, 10, 100, 20, 0, 50, 30, 15]
    names = ["🎭 МАСКА", "🎨 ПАЛИТРА", "👑 КОРОНА", "🖼️ КАРТИНА", 
             "🎁 ПОДАРОК", "✨ КИСТЬ", "🌟 ЗВЕЗДА", "💫 ВДОХНОВЕНИЕ"]
    
    price = prices[sticker_id-1] if 1 <= sticker_id <= 8 else 0
    
    if price == 0:
        await callback.answer(f"✅ Стикер {names[sticker_id-1]} получен!", show_alert=True)
    else:
        await callback.answer(f"💰 Стикер {names[sticker_id-1]} стоит {price} 💎", show_alert=True)

# ========== CALLBACKS ДЛЯ ПРЕМИУМА ==========
@dp.callback_query(F.data.startswith("buy_"))
async def buy_premium(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум ДАЙВИНЧИК", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="👑 Премиум ДАЙВИНЧИК",
        description=f"Премиум на {days} дней",
        payload=f"premium_{days}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])
    
    db.cursor.execute('''
        UPDATE users 
        SET is_premium = 1,
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=days)).isoformat(), user_id))
    db.conn.commit()
    
    await message.answer(
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"✅ ПРЕМИУМ АКТИВИРОВАН!\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        f"На {days} дней\n"
        f"Теперь у тебя {PREMIUM_LIMIT} 👁️ и 💋"
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
🎨══════ ДАЙВИНЧИК ══════🎨
🎭 БОТ ЗАПУЩЕН!
👑 АДМИН: {ADMIN_IDS[0]}
🖼️ СТАТУС: ШЕДЕВР РАБОТАЕТ
💫 ФИЧИ: 14 ШТУК
🎨══════════════════════🎨
""")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
