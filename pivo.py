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
    LabeledPrice, PreCheckoutQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== СТИЛЬ GHOSTIPEEK + ПИВЧИК ==========
STYLE = {
    "name": "👻 ПИВЧИК",
    "header": "👻══════ GHOSTIPEEK ══════👻",
    "divider": "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒",
    "ghost": "👻",
    "beer": "🍺",
    "like": "🖤",
    "mutual": "💀",
    "profile": "⚰️",
    "view": "👁️‍🗨️",
    "premium": "💀",
    "stats": "📿",
    "settings": "⚙️",
    "help": "❓",
    "balance": "🕯️",
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
        self.conn = sqlite3.connect("ghostipeek.db")
        self.cursor = self.conn.cursor()
        self.create_tables()
        print("👻 База данных GHOSTIPEEK подключена")
    
    def create_tables(self):
        # Пользователи (призраки)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghosts (
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
                ghost_power INTEGER DEFAULT 0
            )
        ''')
        
        # Анкеты (призрачные профили)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghost_profiles (
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
                ghost_type TEXT DEFAULT 'Обычный призрак'
            )
        ''')
        
        # Лайки (призрачные касания)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghost_touches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                created_at TEXT,
                is_mutual INTEGER DEFAULT 0,
                chat_opened INTEGER DEFAULT 0,
                UNIQUE(from_user, to_user)
            )
        ''')
        
        # Просмотры (призрачные взгляды)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghost_gazes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                viewed_user_id INTEGER,
                viewed_at TEXT,
                UNIQUE(user_id, viewed_user_id)
            )
        ''')
        
        # Чаты (после взаимного лайка)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghost_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER,
                user2_id INTEGER,
                created_at TEXT,
                last_message TEXT,
                UNIQUE(user1_id, user2_id)
            )
        ''')
        
        self.conn.commit()
    
    # Методы для пользователей
    def get_ghost(self, user_id):
        self.cursor.execute('SELECT * FROM ghosts WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def create_ghost(self, user_id, username, first_name):
        referral_code = f"GHOST{user_id}{random.randint(1000, 9999)}"
        self.cursor.execute('''
            INSERT INTO ghosts (user_id, username, first_name, joined_date, last_active, referral_code, balance, ghost_power)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        ''', (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat(), referral_code))
        self.conn.commit()
    
    def update_last_active(self, user_id):
        self.cursor.execute('UPDATE ghosts SET last_active = ? WHERE user_id = ?', 
                          (datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def add_balance(self, user_id, amount):
        self.cursor.execute('UPDATE ghosts SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()
    
    # Методы для анкет
    def get_profile(self, user_id):
        self.cursor.execute('SELECT * FROM ghost_profiles WHERE user_id = ? AND is_active = 1', (user_id,))
        return self.cursor.fetchone()
    
    def create_profile(self, user_id, name, age, gender, city, about, photo):
        photos = json.dumps([photo])
        ghost_types = ["Обычный призрак", "Полтергейст", "Банши", "Фантом", "Тень"]
        ghost_type = random.choice(ghost_types)
        
        self.cursor.execute('''
            INSERT INTO ghost_profiles (user_id, name, age, gender, city, about, photos, created_at, updated_at, ghost_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, age, gender, city, about, photos, datetime.now().isoformat(), datetime.now().isoformat(), ghost_type))
        
        self.cursor.execute('UPDATE ghosts SET ghost_power = ghost_power + 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return ghost_type
    
    def update_profile(self, user_id, field, value):
        self.cursor.execute(f'UPDATE ghost_profiles SET {field} = ?, updated_at = ? WHERE user_id = ?', 
                          (value, datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def add_photo(self, user_id, photo_id):
        profile = self.get_profile(user_id)
        if profile:
            photos = json.loads(profile[7]) if profile[7] else []
            if len(photos) < 5:
                photos.append(photo_id)
                self.cursor.execute('UPDATE ghost_profiles SET photos = ?, updated_at = ? WHERE user_id = ?',
                                  (json.dumps(photos), datetime.now().isoformat(), user_id))
                self.conn.commit()
                return True
        return False
    
    def delete_profile(self, user_id):
        self.cursor.execute('UPDATE ghost_profiles SET is_active = 0 WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM ghost_touches WHERE from_user = ? OR to_user = ?', (user_id, user_id))
        self.cursor.execute('DELETE FROM ghost_gazes WHERE user_id = ? OR viewed_user_id = ?', (user_id, user_id))
        self.conn.commit()
    
    # Методы для лайков (призрачных касаний) - ТОЛЬКО ВЗАИМНЫЕ
    def add_touch(self, from_user, to_user):
        try:
            self.cursor.execute('''
                INSERT INTO ghost_touches (from_user, to_user, created_at)
                VALUES (?, ?, ?)
            ''', (from_user, to_user, datetime.now().isoformat()))
            
            self.cursor.execute('UPDATE ghosts SET likes_used = likes_used + 1 WHERE user_id = ?', (from_user,))
            self.cursor.execute('UPDATE ghost_profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
            self.conn.commit()
            
            # Проверяем взаимность
            self.cursor.execute('SELECT 1 FROM ghost_touches WHERE from_user = ? AND to_user = ?', (to_user, from_user))
            if self.cursor.fetchone():
                # Взаимный лайк - создаем чат
                self.cursor.execute('''
                    UPDATE ghost_touches SET is_mutual = 1 
                    WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                ''', (from_user, to_user, to_user, from_user))
                
                self.cursor.execute('''
                    INSERT OR IGNORE INTO ghost_chats (user1_id, user2_id, created_at)
                    VALUES (?, ?, ?)
                ''', (min(from_user, to_user), max(from_user, to_user), datetime.now().isoformat()))
                
                self.conn.commit()
                return True  # Взаимный лайк
            return False  # Обычный лайк
        except sqlite3.IntegrityError:
            return None  # Уже лайкал
    
    # Метод для получения чата после взаимного лайка
    def get_chat_partner(self, user_id, other_id):
        self.cursor.execute('''
            SELECT 1 FROM ghost_chats 
            WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
        ''', (user_id, other_id, other_id, user_id))
        return self.cursor.fetchone() is not None
    
    # Методы для поиска
    def get_random_profile(self, user_id):
        self.cursor.execute('''
            SELECT p.*, u.username FROM ghost_profiles p
            JOIN ghosts u ON p.user_id = u.user_id
            WHERE p.user_id != ? 
            AND p.is_active = 1
            AND u.is_banned = 0
            AND p.user_id NOT IN (
                SELECT viewed_user_id FROM ghost_gazes WHERE user_id = ?
            )
            ORDER BY RANDOM()
            LIMIT 1
        ''', (user_id, user_id))
        return self.cursor.fetchone()
    
    def get_top_likes(self, limit=10):
        self.cursor.execute('''
            SELECT p.name, p.likes_count, p.photos, u.user_id, p.ghost_type
            FROM ghost_profiles p
            JOIN ghosts u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.likes_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_top_views(self, limit=10):
        self.cursor.execute('''
            SELECT p.name, p.views_count, p.photos, u.user_id, p.ghost_type
            FROM ghost_profiles p
            JOIN ghosts u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.views_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_nearby(self, city, user_id):
        self.cursor.execute('''
            SELECT p.name, p.age, p.gender, p.photos, p.ghost_type
            FROM ghost_profiles p
            JOIN ghosts u ON p.user_id = u.user_id
            WHERE u.city = ? AND p.user_id != ? AND p.is_active = 1
            ORDER BY RANDOM()
            LIMIT 5
        ''', (city, user_id))
        return self.cursor.fetchall()

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

# ========== КЛАВИАТУРЫ В СТИЛЕ GHOSTIPEEK ==========
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="⚰️ МОЯ ТЕНЬ"), KeyboardButton(text="👁️‍🗨️ ПРИЗРАКИ")],
        [KeyboardButton(text="💀 ПРЕМИУМ"), KeyboardButton(text="📿 МОЯ АУРА")],
        [KeyboardButton(text="🔥 ТОП ПРИЗРАКОВ"), KeyboardButton(text="🎁 ВЫЗОВ")],
        [KeyboardButton(text="🎲 ИГРЫ ТЕНЕЙ"), KeyboardButton(text="💬 ШЕПОТ")],
        [KeyboardButton(text="🎂 ДНИ ТЬМЫ"), KeyboardButton(text="📍 РЯДОМ")],
        [KeyboardButton(text="🎨 СТИКЕРЫ"), KeyboardButton(text="⚙️ РИТУАЛЫ")],
        [KeyboardButton(text="🕯️ МОЩЬ"), KeyboardButton(text="❓ ПОМОЩЬ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    kb = [[KeyboardButton(text="◀️ НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    kb = [
        [KeyboardButton(text="МУЖСКОЙ ПРИЗРАК"), KeyboardButton(text="ЖЕНСКИЙ ПРИЗРАК")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    ghost = db.get_ghost(user_id)
    if not ghost:
        db.create_ghost(user_id, message.from_user.username, message.from_user.first_name)
        
        args = message.text.split()
        if len(args) > 1:
            master_id = db.process_apprentice(args[1], user_id)
            if master_id:
                await bot.send_message(
                    master_id,
                    f"🎁 НОВЫЙ ПРИЗРАК!\n\n"
                    f"Призрак @{message.from_user.username} появился по твоему вызову!\n"
                    f"Начислено 50 🕯️ на баланс!"
                )
    
    db.update_last_active(user_id)
    
    welcome_text = f"""
👻══════ GHOSTIPEEK ══════👻

🖤 {message.from_user.first_name}, ты вошел в мир призраков...

Здесь тени ищут друг друга,
а настоящее общение возможно только
когда две души почувствуют друг друга.

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👇 ВОЙДИ В ТЕНЬ:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== ⚰️ МОЯ ТЕНЬ (МОЯ АНКЕТА) ==========
@dp.message(F.text.in_(["⚰️ МОЯ ТЕНЬ", "МОЯ ТЕНЬ"]))
async def my_profile(message: Message):
    user_id = message.from_user.id
    profile = db.get_profile(user_id)
    
    if not profile:
        await message.answer(
            f"❌ У тебя ещё нет тени!\n"
            f"Нажми /create чтобы создать"
        )
        return
    
    views = db.cursor.execute('SELECT COUNT(*) FROM ghost_gazes WHERE viewed_user_id = ?', (user_id,)).fetchone()[0]
    likes = db.cursor.execute('SELECT COUNT(*) FROM ghost_touches WHERE to_user = ?', (user_id,)).fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM ghost_touches WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]
    
    ghost = db.get_ghost(user_id)
    is_premium = ghost[3] if ghost else 0
    premium_badge = f" 💀" if is_premium else ""
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
⚰️ ТВОЯ ТЕНЬ{premium_badge}
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👤 Имя: {profile[2]}
📅 Возраст: {profile[3]}
⚥ Пол: {profile[4]}
🏙 Город: {profile[5]}
👻 Тип: {profile[13] if len(profile) > 13 else 'Обычный призрак'}

📝 Шепот:
{profile[6]}

📸 Теней: {len(photos)}

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
📿 АУРА:
👁️‍🗨️ Призраков видели: {views}
🖤 Касаний: {likes}
💀 Взаимных: {mutual}
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ ИЗМЕНИТЬ ТЕНЬ", callback_data="edit_menu")
    builder.button(text="📸 ДОБАВИТЬ ТЕНЬ", callback_data="add_photo")
    builder.button(text="🗑 РАЗВЕЯТЬ", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if main_photo:
        await message.answer_photo(
            photo=main_photo,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== 👁️‍🗨️ ПРИЗРАКИ (СМОТРЕТЬ) ==========
@dp.message(F.text.in_(["👁️‍🗨️ ПРИЗРАКИ", "ПРИЗРАКИ"]))
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    if not db.get_profile(user_id):
        await message.answer("❌ Сначала создай свою тень через /create")
        return
    
    ghost = db.get_ghost(user_id)
    is_premium = ghost[3] if ghost else 0
    views_used = ghost[5] if ghost else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(f"❌ Лимит призраков исчерпан ({limit})\nКупи 💀 ПРЕМИУМ")
        return
    
    profile = db.get_random_profile(user_id)
    
    if not profile:
        await message.answer("👻 Ты видел всех призраков! Зайди позже")
        return
    
    db.cursor.execute('''
        INSERT INTO ghost_gazes (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    db.cursor.execute('UPDATE ghosts SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    db.cursor.execute('UPDATE ghost_profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    db.conn.commit()
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else None
    
    gender_emoji = "👻" if profile[4] == "Мужской" else "👻"
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
{gender_emoji} {profile[2]}, {profile[3]}
🏙 {profile[5]}
👻 Тип: {profile[13] if len(profile) > 13 else 'Обычный призрак'}

📝 Шепот:
{profile[6]}

🖤 Касаний: {profile[10]} | 👁️‍🗨️ Видели: {profile[9]}
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🖤 КОСНУТЬСЯ", callback_data=f"like_{profile[1]}")
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

# ========== 🖤 КАСАНИЯ (ЛАЙКИ) - ТОЛЬКО ВЗАИМНЫЕ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer("❌ Нельзя коснуться себя!", show_alert=True)
        return
    
    ghost = db.get_ghost(from_user)
    is_premium = ghost[3] if ghost else 0
    likes_used = ghost[4] if ghost else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит касаний ({limit}) исчерпан!", show_alert=True)
        return
    
    result = db.add_touch(from_user, to_user)
    
    if result is None:
        await callback.answer("❌ Ты уже касался этого призрака", show_alert=True)
    elif result is True:
        # ВЗАИМНЫЙ ЛАЙК - можно писать!
        await callback.answer("💀 ВЗАИМНОЕ КАСАНИЕ! ЧАТ ОТКРЫТ!", show_alert=True)
        
        to_profile = db.get_profile(to_user)
        to_name = to_profile[2] if to_profile else "Призрак"
        to_user_data = db.get_ghost(to_user)
        to_username = to_user_data[1] if to_user_data else None
        
        from_profile = db.get_profile(from_user)
        from_name = from_profile[2] if from_profile else "Призрак"
        
        # Создаем кнопку для перехода в ЛС
        if to_username:
            builder1 = InlineKeyboardBuilder()
            builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
            builder1.button(text="👁️‍🗨️ ПРОДОЛЖИТЬ", callback_data="next_profile")
            
            await bot.send_message(
                from_user,
                f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
                f"💀 ВЗАИМНОЕ КАСАНИЕ!\n"
                f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
                f"Ты почувствовал присутствие {to_name}!\n\n"
                f"Теперь вы можете общаться!",
                reply_markup=builder1.as_markup()
            )
        
        from_user_data = db.get_ghost(from_user)
        from_username = from_user_data[1] if from_user_data else None
        
        if from_username:
            builder2 = InlineKeyboardBuilder()
            builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
            builder2.button(text="👁️‍🗨️ ПРОДОЛЖИТЬ", callback_data="next_profile")
            
            await bot.send_message(
                to_user,
                f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
                f"💀 ВЗАИМНОЕ КАСАНИЕ!\n"
                f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
                f"Ты почувствовал присутствие {from_name}!\n\n"
                f"Теперь вы можете общаться!",
                reply_markup=builder2.as_markup()
            )
    else:
        await callback.answer("🖤 ТЫ КОСНУЛСЯ ПРИЗРАКА")

# ========== 💀 ПРЕМИУМ ==========
@dp.message(F.text.in_(["💀 ПРЕМИУМ", "ПРЕМИУМ"]))
async def show_premium(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
💀 ПРЕМИУМ GHOSTIPEEK
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

📊 ЛИМИТЫ ПРИЗРАКОВ:
• Обычный призрак: {FREE_LIMIT} 👁️‍🗨️/🖤
• Высший призрак: {PREMIUM_LIMIT} 👁️‍🗨️/🖤

✨ СИЛА ПРЕМИУМ:
• 💀 Корона в тени
• 👻 Эксклюзивные типы призраков
• 🔥 Показ в топе
• 🕯️ Особая аура

💰 ЦЕНА:
• 50 🕯️ = 1 день
• 250 🕯️ = 7 дней
• 1000 🕯️ = 30 дней
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🕯️ 50 (1 день)", callback_data="buy_50")
    builder.button(text="🕯️ 250 (7 дней)", callback_data="buy_250")
    builder.button(text="🕯️ 1000 (30 дней)", callback_data="buy_1000")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 📿 МОЯ АУРА (СТАТИСТИКА) ==========
@dp.message(F.text.in_(["📿 МОЯ АУРА", "МОЯ АУРА"]))
async def show_stats(message: Message):
    user_id = message.from_user.id
    
    viewed = db.cursor.execute('SELECT COUNT(*) FROM ghost_gazes WHERE user_id = ?', (user_id,)).fetchone()[0]
    viewed_me = db.cursor.execute('SELECT COUNT(*) FROM ghost_gazes WHERE viewed_user_id = ?', (user_id,)).fetchone()[0]
    likes_given = db.cursor.execute('SELECT COUNT(*) FROM ghost_touches WHERE from_user = ?', (user_id,)).fetchone()[0]
    likes_received = db.cursor.execute('SELECT COUNT(*) FROM ghost_touches WHERE to_user = ?', (user_id,)).fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM ghost_touches WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]
    
    ghost = db.get_ghost(user_id)
    is_premium = ghost[3] if ghost else 0
    views_used = ghost[5] if ghost else 0
    likes_used = ghost[4] if ghost else 0
    ghost_power = ghost[16] if ghost and len(ghost) > 16 else 0
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
📿 ТВОЯ АУРА
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👻 Сила призрака: {ghost_power}
👁️‍🗨️ Ты видел призраков: {viewed}
👁️‍🗨️ Тебя видели: {viewed_me}
🖤 Ты коснулся: {likes_given}
🖤 Тебя коснулись: {likes_received}
💀 Взаимных касаний: {mutual}

📈 ОСТАЛОСЬ СИЛЫ:
• 👁️‍🗨️ {limit - views_used}
• 🖤 {limit - likes_used}
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

# ========== 🔥 ТОП ПРИЗРАКОВ ==========
@dp.message(F.text.in_(["🔥 ТОП ПРИЗРАКОВ", "ТОП ПРИЗРАКОВ"]))
async def show_top(message: Message):
    top_likes = db.get_top_likes(5)
    top_views = db.get_top_views(5)
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🔥 ТОП ПРИЗРАКОВ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

🖤 ТОП ПО КАСАНИЯМ:
"""
    
    for i, profile in enumerate(top_likes, 1):
        text += f"{i}. {profile[0]} ({profile[4]}) - {profile[1]} 🖤\n"
    
    text += f"\n👁️‍🗨️ ТОП ПО ПРОСМОТРАМ:\n"
    
    for i, profile in enumerate(top_views, 1):
        text += f"{i}. {profile[0]} ({profile[4]}) - {profile[1]} 👁️‍🗨️\n"
    
    text += f"\n▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
    
    await message.answer(text)

# ========== 🎁 ВЫЗОВ (РЕФЕРАЛЫ) ==========
@dp.message(F.text.in_(["🎁 ВЫЗОВ", "ВЫЗОВ"]))
async def show_referrals(message: Message):
    user_id = message.from_user.id
    ghost = db.get_ghost(user_id)
    
    if not ghost:
        return
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={ghost[8]}"  # referral_code
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🎁 ВЫЗОВ ПРИЗРАКОВ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

📊 СТАТИСТИКА:
• Вызвано призраков: {ghost[9]} чел.
• Накоплено силы: {ghost[10]} 🕯️

💰 НАГРАДЫ:
• За каждого призрака: 50 🕯️
• За 10 призраков: +1 день 💀
• За 50 призраков: +7 дней 💀

🔗 ТВОЙ РИТУАЛ:
{referral_link}

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

# ========== 🎲 ИГРЫ ТЕНЕЙ ==========
@dp.message(F.text.in_(["🎲 ИГРЫ ТЕНЕЙ", "ИГРЫ ТЕНЕЙ"]))
async def show_games(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🎲 ИГРЫ ТЕНЕЙ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👻 УГАДАЙ ПРИЗРАКА
Определи тип призрака

🎭 ТЕНЕВАЯ ВИКТОРИНА
Вопросы о сверхъестественном

🖤 КАСАНИЕ ТЬМЫ
Угадай эмоцию по тени

💀 РИТУАЛ
Собери заклинание

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👻 УГАДАЙ ПРИЗРАКА", callback_data="game_ghost")
    builder.button(text="🎭 ТЕНЕВАЯ ВИКТОРИНА", callback_data="game_quiz")
    builder.button(text="🖤 КАСАНИЕ ТЬМЫ", callback_data="game_touch")
    builder.button(text="💀 РИТУАЛ", callback_data="game_ritual")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 💬 ШЕПОТ (ЧАТЫ) ==========
@dp.message(F.text.in_(["💬 ШЕПОТ", "ШЕПОТ"]))
async def show_chats(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
💬 ШЕПОТ ПРИЗРАКОВ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👻 ОБЩИЙ ШЕПОТ
🖤 ТЕНЕВОЙ ЧАТ
💀 РИТУАЛЬНЫЙ
🎭 МИСТИЧЕСКИЙ
👁️‍🗨️ ПРОРОЧЕСКИЙ
🌑 НОЧНОЙ

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👻 ОБЩИЙ", callback_data="chat_general")
    builder.button(text="🖤 ТЕНЕВОЙ", callback_data="chat_shadow")
    builder.button(text="💀 РИТУАЛЬНЫЙ", callback_data="chat_ritual")
    builder.button(text="🎭 МИСТИЧЕСКИЙ", callback_data="chat_mystic")
    builder.button(text="👁️‍🗨️ ПРОРОЧЕСКИЙ", callback_data="chat_prophet")
    builder.button(text="🌑 НОЧНОЙ", callback_data="chat_night")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== 🎂 ДНИ ТЬМЫ (ДНИ РОЖДЕНИЯ) ==========
@dp.message(F.text.in_(["🎂 ДНИ ТЬМЫ", "ДНИ ТЬМЫ"]))
async def show_birthdays(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🎂 ДНИ ТЬМЫ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

📅 СЕГОДНЯ:
Сегодня нет дней тьмы

📅 БЛИЖАЙШИЕ:
Скоро появятся...

Чтобы добавить свой день:
/setbirthday ДД.ММ.ГГГГ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

@dp.message(Command("setbirthday"))
async def set_birthday(message: Message):
    try:
        date_str = message.text.replace("/setbirthday", "").strip()
        birth_date = datetime.strptime(date_str, "%d.%m.%Y")
        
        age = (datetime.now() - birth_date).days // 365
        if db.get_profile(message.from_user.id):
            db.update_profile(message.from_user.id, "age", age)
        
        await message.answer(
            f"✅ День тьмы сохранен!\n"
            f"Возраст: {age}"
        )
    except:
        await message.answer("❌ Неверный формат. Используй: /setbirthday 01.01.1990")

# ========== 📍 РЯДОМ ==========
@dp.message(F.text.in_(["📍 РЯДОМ", "РЯДОМ"]))
async def find_nearby(message: Message):
    user_id = message.from_user.id
    ghost = db.get_ghost(user_id)
    
    if not ghost or not ghost[11]:  # city
        await message.answer(
            f"⚠️ Укажи свой город!\n"
            f"Используй /setcity НазваниеГорода"
        )
        return
    
    nearby = db.get_nearby(ghost[11], user_id)
    
    if not nearby:
        await message.answer(
            f"❌ В твоем городе пока нет призраков!\n"
            f"Вызови их через 🎁 ВЫЗОВ"
        )
        return
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
📍 ПРИЗРАКИ РЯДОМ ({ghost[11]})
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

"""
    
    for name, age, gender, photos, ghost_type in nearby:
        text += f"👻 {name}, {age} - {ghost_type}\n"
    
    text += f"\n▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
    
    await message.answer(text)

@dp.message(Command("setcity"))
async def set_city(message: Message):
    city = message.text.replace("/setcity", "").strip()
    if not city:
        await message.answer("❌ Напиши: /setcity НазваниеГорода")
        return
    
    db.cursor.execute('UPDATE ghosts SET city = ? WHERE user_id = ?', (city, message.from_user.id))
    db.conn.commit()
    
    await message.answer(f"✅ Город {city} сохранен!")

# ========== 🎨 СТИКЕРЫ ==========
@dp.message(F.text.in_(["🎨 СТИКЕРЫ", "СТИКЕРЫ"]))
async def show_stickers(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🎨 КОЛЛЕКЦИЯ ТЕНЕЙ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

👻 ПРИЗРАК - 0 🕯️
🖤 ТЕНЬ - 10 🕯️
💀 ЧЕРЕП - 100 🕯️ (💀)
🌙 ЛУНА - 20 🕯️
🎃 ТЫКВА - 0 🕯️
🕷️ ПАУК - 50 🕯️
🕸️ ПАУТИНА - 30 🕯️
🦇 ЛЕТУЧАЯ МЫШЬ - 15 🕯️

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👻 ПРИЗРАК", callback_data="buy_sticker_1")
    builder.button(text="🖤 ТЕНЬ", callback_data="buy_sticker_2")
    builder.button(text="💀 ЧЕРЕП", callback_data="buy_sticker_3")
    builder.button(text="🌙 ЛУНА", callback_data="buy_sticker_4")
    builder.button(text="🎃 ТЫКВА", callback_data="buy_sticker_5")
    builder.button(text="🕷️ ПАУК", callback_data="buy_sticker_6")
    builder.button(text="🕸️ ПАУТИНА", callback_data="buy_sticker_7")
    builder.button(text="🦇 ЛЕТУЧАЯ МЫШЬ", callback_data="buy_sticker_8")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup())

# ========== ⚙️ РИТУАЛЫ (НАСТРОЙКИ) ==========
@dp.message(F.text.in_(["⚙️ РИТУАЛЫ", "РИТУАЛЫ"]))
async def show_settings(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
⚙️ РИТУАЛЫ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

/setcity Город - указать город
/setbirthday ДД.ММ.ГГГГ - день тьмы
/create - создать тень

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

# ========== 🕯️ МОЩЬ (БАЛАНС) ==========
@dp.message(F.text.in_(["🕯️ МОЩЬ", "МОЩЬ"]))
async def show_balance(message: Message):
    user_id = message.from_user.id
    ghost = db.get_ghost(user_id)
    balance = ghost[7] if ghost else 0
    
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
🕯️ ТВОЯ МОЩЬ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

У тебя: {balance} 🕯️

Пополнить через 💀 ПРЕМИУМ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

# ========== ❓ ПОМОЩЬ ==========
@dp.message(F.text.in_(["❓ ПОМОЩЬ", "ПОМОЩЬ"]))
async def show_help(message: Message):
    text = f"""
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
❓ ПОМОЩЬ
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒

📝 РИТУАЛЫ:
/create - создать тень
/setcity - указать город
/setbirthday - день тьмы

⚰️ МОЯ ТЕНЬ - просмотр/редактирование
👁️‍🗨️ ПРИЗРАКИ - смотреть анкеты
🖤 КОСНУТЬСЯ - поставить касание
💀 ВЗАИМНОЕ - можно писать

🔥 ТОП ПРИЗРАКОВ - самые популярные
🎁 ВЫЗОВ - приглашай друзей
🎲 ИГРЫ ТЕНЕЙ - игры для знакомств
💬 ШЕПОТ - общение

⚠️ ПРАВИЛА:
• Только настоящие призраки
• Без черной магии
• Возраст 18+

👻 По вопросам: @admin
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
"""
    
    await message.answer(text)

# ========== ◀️ НАЗАД ==========
@dp.message(F.text.in_(["◀️ НАЗАД", "НАЗАД"]))
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# ========== СОЗДАНИЕ ТЕНИ (АНКЕТЫ) ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.get_profile(user_id):
        await message.answer(
            f"❌ У тебя уже есть тень!\n"
            f"Если хочешь создать новую, развей старую."
        )
        return
    
    await message.answer(
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
        f"👻 СОЗДАНИЕ ТЕНИ\n"
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
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
    if message.text.upper() not in ["МУЖСКОЙ ПРИЗРАК", "ЖЕНСКИЙ ПРИЗРАК", "МУЖСКОЙ", "ЖЕНСКИЙ"]:
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
        f"📝 Опиши свою тень\n"
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
        f"📸 Отправь фото своей тени",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    ghost_type = db.create_profile(
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
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
        f"✅ ТЕНЬ СОЗДАНА!\n"
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
        f"Тип: {ghost_type}\n\n"
        f"Теперь ищи других призраков 👁️‍🗨️",
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
        caption=f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n✏️ ИЗМЕНЕНИЕ ТЕНИ\n▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\nЧто хочешь изменить?",
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
            f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
            f"✏️ ИЗМЕНЕНИЕ ПОЛА\n"
            f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
            f"Выбери новый пол:",
            reply_markup=get_gender_keyboard()
        )
    else:
        field_names = {"name": "ИМЯ", "age": "ВОЗРАСТ", "city": "ГОРОД", "about": "ОПИСАНИЕ"}
        await callback.message.answer(
            f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
            f"✏️ ИЗМЕНЕНИЕ {field_names.get(field, '')}\n"
            f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
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
        if message.text.upper() not in ["МУЖСКОЙ ПРИЗРАК", "ЖЕНСКИЙ ПРИЗРАК", "МУЖСКОЙ", "ЖЕНСКИЙ"]:
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
    await message.answer("⚰️ Возвращаемся к тени...", reply_markup=get_main_keyboard())
    await my_profile(message)

@dp.callback_query(F.data == "add_photo")
async def add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
        f"📸 ДОБАВЛЕНИЕ ТЕНИ\n"
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
        f"Отправь фото (можно добавить до 5 шт)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photos)

@dp.message(ProfileStates.photos, F.photo)
async def process_add_photo(message: Message, state: FSMContext):
    result = db.add_photo(message.from_user.id, message.photo[-1].file_id)
    
    if result:
        await message.answer(f"✅ Тень добавлена!")
    else:
        await message.answer(f"❌ Ошибка (макс. 5 теней)")
        await state.clear()
        await my_profile(message)

# ========== УДАЛЕНИЕ ==========
@dp.callback_query(F.data == "delete_profile")
async def delete_profile_confirm(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ДА, РАЗВЕЯТЬ", callback_data="confirm_delete")
    builder.button(text="◀️ ОТМЕНА", callback_data="back_to_profile")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption=f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
                f"⚠️ РАЗВЕЯНИЕ ТЕНИ\n"
                f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
                f"Ты уверен? Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_delete")
async def delete_profile(callback: CallbackQuery):
    db.delete_profile(callback.from_user.id)
    
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Тень развеяна!\n"
        f"Чтобы создать новую, нажми /create",
        reply_markup=get_main_keyboard()
    )

# ========== CALLBACKS ДЛЯ ИГР ==========
@dp.callback_query(F.data.startswith("game_"))
async def game_callback(callback: CallbackQuery):
    game = callback.data.replace("game_", "")
    
    games = {
        "ghost": "👻 Угадай призрака",
        "quiz": "🎭 Теневая викторина",
        "touch": "🖤 Касание тьмы",
        "ritual": "💀 Ритуал"
    }
    
    await callback.message.answer(f"{games.get(game, '🎲')} скоро будет доступна!")
    await callback.answer()

# ========== CALLBACKS ДЛЯ ЧАТОВ ==========
@dp.callback_query(F.data.startswith("chat_"))
async def chat_callback(callback: CallbackQuery):
    chat = callback.data.replace("chat_", "")
    
    chats = {
        "general": "👻 Общий шепот",
        "shadow": "🖤 Теневой чат",
        "ritual": "💀 Ритуальный",
        "mystic": "🎭 Мистический",
        "prophet": "👁️‍🗨️ Пророческий",
        "night": "🌑 Ночной"
    }
    
    await callback.message.answer(
        f"💬 Чат '{chats.get(chat, 'Шепот')}' скоро будет доступен!\n"
        f"Следи за обновлениями!"
    )
    await callback.answer()

# ========== CALLBACKS ДЛЯ СТИКЕРОВ ==========
@dp.callback_query(F.data.startswith("buy_sticker_"))
async def buy_sticker(callback: CallbackQuery):
    sticker_id = int(callback.data.replace("buy_sticker_", ""))
    prices = [0, 10, 100, 20, 0, 50, 30, 15]
    names = ["👻 ПРИЗРАК", "🖤 ТЕНЬ", "💀 ЧЕРЕП", "🌙 ЛУНА", 
             "🎃 ТЫКВА", "🕷️ ПАУК", "🕸️ ПАУТИНА", "🦇 ЛЕТУЧАЯ МЫШЬ"]
    
    price = prices[sticker_id-1] if 1 <= sticker_id <= 8 else 0
    
    if price == 0:
        await callback.answer(f"✅ Стикер {names[sticker_id-1]} получен!", show_alert=True)
    else:
        await callback.answer(f"💰 Стикер {names[sticker_id-1]} стоит {price} 🕯️", show_alert=True)

# ========== CALLBACKS ДЛЯ ПРЕМИУМА ==========
@dp.callback_query(F.data.startswith("buy_"))
async def buy_premium(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум GHOSTIPEEK", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💀 Премиум GHOSTIPEEK",
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
        UPDATE ghosts 
        SET is_premium = 1,
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=days)).isoformat(), user_id))
    db.conn.commit()
    
    await message.answer(
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n"
        f"✅ ПРЕМИУМ АКТИВИРОВАН!\n"
        f"▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒\n\n"
        f"На {days} дней\n"
        f"Теперь у тебя {PREMIUM_LIMIT} 👁️‍🗨️ и 🖤"
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
👻══════ GHOSTIPEEK ══════👻
👻 БОТ ЗАПУЩЕН!
💀 АДМИН: {ADMIN_IDS[0]}
🖤 СТАТУС: МИСТИКА РАБОТАЕТ
👁️‍🗨️ ФИЧИ: 14 ШТУК
👻═══════════════════════👻
""")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
