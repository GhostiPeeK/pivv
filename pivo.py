import logging
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
import random
from contextlib import contextmanager
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.types import LabeledPrice, PreCheckoutQuery

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]  # Твой ID

PREMIUM_PRICE_STARS = 50  # Цена в звёздах Telegram
FREE_LIMIT = 250
PREMIUM_LIMIT = 1500

MIN_AGE = 18
MAX_AGE = 100
REQUIRED_PHOTOS = 3
ACCOUNT_MIN_AGE_DAYS = 30

# ========== ФУНКЦИЯ ДЛЯ ЭКРАНИРОВАНИЯ MD ==========
def escape_md(text):
    """Экранирует специальные символы для MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("pivchik.db", check_same_thread=False)
        self._create_tables()
        print("✅ База данных ПИВЧИК подключена")
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                likes_used INTEGER DEFAULT 0,
                views_used INTEGER DEFAULT 0,
                joined_date TEXT,
                last_active TEXT,
                is_blocked INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER,
                balance INTEGER DEFAULT 0,
                total_donated INTEGER DEFAULT 0
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
                interests TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
        
        # Взаимные лайки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutual_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 INTEGER,
                user2 INTEGER,
                created_at TEXT,
                UNIQUE(user1, user2)
            )
        ''')
        
        # Транзакции
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_method TEXT,
                payment_id TEXT,
                status TEXT,
                created_at TEXT
            )
        ''')
        
        self.conn.commit()
    
    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

db = Database()

# ========== FSM ==========
class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_city = State()
    waiting_for_about = State()
    waiting_for_photos = State()
    waiting_for_interests = State()
    waiting_for_edit_value = State()
    waiting_for_complaint = State()
    waiting_for_broadcast = State()
    waiting_for_report_reply = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== УДОБНАЯ REPLY КЛАВИАТУРА ==========
def get_main_keyboard():
    """Главная клавиатура которая всегда внизу"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🍺 МОЯ АНКЕТА"))
    builder.add(KeyboardButton(text="👀 СМОТРЕТЬ"))
    builder.add(KeyboardButton(text="⭐ ПРЕМИУМ"))
    builder.add(KeyboardButton(text="📊 СТАТИСТИКА"))
    builder.add(KeyboardButton(text="⚙️ НАСТРОЙКИ"))
    builder.add(KeyboardButton(text="❓ ПОМОЩЬ"))
    builder.add(KeyboardButton(text="💰 ПОПОЛНИТЬ"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🍺 ГЛАВНОЕ МЕНЮ"))
    return builder.as_markup(resize_keyboard=True)

# ========== INLINE МЕНЮ ==========
def main_menu(user_id):
    """Инлайн меню"""
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.profile_id, u.is_premium, u.views_used, u.likes_used, u.balance
        FROM users u 
        LEFT JOIN profiles p ON u.user_id = p.user_id 
        WHERE u.user_id = ?
    ''', (user_id,))
    data = cursor.fetchone()
    
    has_profile = data and data[0] is not None
    is_premium = data[1] if data else False
    views_used = data[2] if data else 0
    likes_used = data[3] if data else 0
    balance = data[4] if data else 0
    
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    builder = InlineKeyboardBuilder()
    
    if has_profile:
        builder.button(text=f"👤 МОЯ АНКЕТА", callback_data="my_profile")
        builder.button(text=f"👀 СМОТРЕТЬ ({limit - views_used})", callback_data="view_profiles")
    else:
        builder.button(text="🍺 СОЗДАТЬ АНКЕТУ", callback_data="create_profile")
    
    builder.button(text="⭐ ПРЕМИУМ", callback_data="premium_info")
    builder.button(text="📊 СТАТИСТИКА", callback_data="my_stats")
    builder.button(text=f"💰 БАЛАНС: {balance} ⭐", callback_data="balance")
    builder.button(text="⚙️ НАСТРОЙКИ", callback_data="settings")
    builder.button(text="❓ ПОМОЩЬ", callback_data="help")
    
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def profile_menu():
    """Меню анкеты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ РЕДАКТИРОВАТЬ", callback_data="edit_profile_menu")
    builder.button(text="📸 ДОБАВИТЬ ФОТО", callback_data="add_photos")
    builder.button(text="🎯 ИНТЕРЕСЫ", callback_data="edit_interests")
    builder.button(text="💔 УДАЛИТЬ", callback_data="delete_profile")
    builder.button(text="📊 СТАТИСТИКА", callback_data="my_stats")
    builder.button(text="🍺 ГЛАВНОЕ МЕНЮ", callback_data="back_to_main")
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def edit_profile_menu():
    """Меню редактирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 Имя", callback_data="edit_name")
    builder.button(text="📅 Возраст", callback_data="edit_age")
    builder.button(text="👤 Пол", callback_data="edit_gender")
    builder.button(text="🏙 Город", callback_data="edit_city")
    builder.button(text="📝 О себе", callback_data="edit_about")
    builder.button(text="🎯 Интересы", callback_data="edit_interests")
    builder.button(text="🖼 Фото", callback_data="edit_photos")
    builder.button(text="🍺 НАЗАД", callback_data="my_profile")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

def premium_menu():
    """Меню премиума"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 STARS (1 день)", callback_data="buy_stars_50")
    builder.button(text="⭐ 250 STARS (7 дней)", callback_data="buy_stars_250")
    builder.button(text="⭐ 1000 STARS (30 дней)", callback_data="buy_stars_1000")
    builder.button(text="₿ КРИПТА", callback_data="buy_crypto")
    builder.button(text="🍺 НАЗАД", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ REPLY КЛАВИАТУРЫ ==========
@dp.message(F.text == "🍺 ГЛАВНОЕ МЕНЮ")
async def reply_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

@dp.message(F.text == "🍺 МОЯ АНКЕТА")
async def reply_my_profile(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            "❌ У тебя ещё нет анкеты.\nНажни '🍺 СОЗДАТЬ АНКЕТУ' в меню ниже:",
            reply_markup=get_main_keyboard()
        )
        await message.answer(
            "🍺 Главное меню:",
            reply_markup=main_menu(user_id)
        )
        return
    
    await show_my_profile(message, user_id)

async def show_my_profile(message: Message, user_id: int):
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.*, u.is_premium, u.views_used, u.likes_used, u.username
        FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        return
    
    photos = json.loads(profile[7])
    interests = json.loads(profile[8]) if profile[8] else []
    is_premium = profile[-4]
    views_used = profile[-3]
    likes_used = profile[-2]
    username = profile[-1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    premium_badge = " ⭐" if is_premium else ""
    interests_text = ", ".join(interests) if interests else "Не указаны"
    
    text = (
        f"🍺 Твоя анкета{premium_badge}\n\n"
        f"👤 Имя: {profile[2]}\n"
        f"📅 Возраст: {profile[3]}\n"
        f"⚥ Пол: {profile[4]}\n"
        f"🏙 Город: {profile[5]}\n"
        f"📝 О себе: {profile[6]}\n"
        f"🎯 Интересы: {interests_text}\n"
        f"🖼 Фото: {len(photos)} шт.\n"
        f"📱 Username: @{username if username else 'нет'}\n\n"
        f"📊 Статистика:\n"
        f"• 👁 Просмотров: {profile[11]}\n"
        f"• ❤️ Лайков: {profile[12]}\n"
        f"• 📈 Осталось просмотров: {limit - views_used}\n"
        f"• 📈 Осталось лайков: {limit - likes_used}"
    )
    
    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=text,
            reply_markup=profile_menu()
        )
    else:
        await message.answer(
            text,
            reply_markup=profile_menu()
        )

@dp.message(F.text == "👀 СМОТРЕТЬ")
async def reply_view_profiles(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await message.answer(
            "❌ Сначала создай анкету! Нажми '🍺 СОЗДАТЬ АНКЕТУ'",
            reply_markup=get_main_keyboard()
        )
        return
    
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    is_premium, views_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(
            f"❌ Лимит просмотров исчерпан ({limit})\nКупи ПРЕМИУМ для увеличения лимита!",
            reply_markup=get_main_keyboard()
        )
        return
    
    cursor.execute('''
        SELECT p.*, u.username FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id != ? 
        AND p.is_active = 1
        AND p.user_id NOT IN (
            SELECT viewed_user_id FROM views WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    ''', (user_id, user_id))
    
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            "🍺 Ты посмотрел все анкеты! Заходи позже, появятся новые",
            reply_markup=get_main_keyboard()
        )
        return
    
    cursor.execute('''
        INSERT OR IGNORE INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('''
        UPDATE users SET views_used = views_used + 1 WHERE user_id = ?
    ''', (user_id,))
    
    cursor.execute('''
        UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?
    ''', (profile[1],))
    
    db.conn.commit()
    
    photos = json.loads(profile[7])
    interests = json.loads(profile[8]) if profile[8] else []
    interests_text = ", ".join(interests) if interests else "Не указаны"
    
    text = (
        f"🍺 {profile[2]}, {profile[3]}\n"
        f"⚥ Пол: {profile[4]}\n"
        f"🏙 Город: {profile[5]}\n"
        f"🎯 Интересы: {interests_text}\n\n"
        f"📝 {profile[6]}\n\n"
        f"❤️ Лайков: {profile[11]} | 👁 Просмотров: {profile[10]}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ЛАЙКНУТЬ", callback_data=f"like_{profile[1]}")
    builder.button(text="⏭ ДАЛЬШЕ", callback_data="view_profiles")
    
    if profile[-1]:
        builder.button(text=f"📱 НАПИСАТЬ @{profile[-1]}", url=f"https://t.me/{profile[-1]}")
    
    builder.button(text="⚠️ ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    
    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(
            text,
            reply_markup=builder.as_markup()
        )

@dp.message(F.text == "⭐ ПРЕМИУМ")
async def reply_premium(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0]:
        until = datetime.fromisoformat(user[1]).strftime("%d.%m.%Y") if user[1] else "бессрочно"
        text = (
            f"⭐ У ТЕБЯ ПРЕМИУМ!\n\n"
            f"📅 Действует до: {until}\n\n"
            f"Твои бонусы:\n"
            f"• 🍺 {PREMIUM_LIMIT} просмотров\n"
            f"• 🍺 {PREMIUM_LIMIT} лайков\n"
            f"• ⭐ Значок в анкете\n"
            f"• 🔥 Показ в топе"
        )
    else:
        text = (
            f"⭐ ПРЕМИУМ ПИВЧИК\n\n"
            f"Лимиты:\n"
            f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
            f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
            f"Бонусы:\n"
            f"• 🍺 Больше анкет\n"
            f"• ⭐ Значок в профиле\n"
            f"• 🔥 Показ в топе\n\n"
            f"💰 Цена:\n"
            f"• 50 ⭐ = 1 день\n"
            f"• 250 ⭐ = 7 дней\n"
            f"• 1000 ⭐ = 30 дней\n\n"
            f"Хочешь больше возможностей?"
        )
    
    await message.answer(
        text,
        reply_markup=premium_menu()
    )

@dp.message(F.text == "📊 СТАТИСТИКА")
async def reply_stats(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT 
            u.is_premium,
            u.views_used,
            u.likes_used,
            COALESCE(p.views_count, 0),
            COALESCE(p.likes_count, 0),
            (SELECT COUNT(*) FROM views WHERE user_id = ?) as viewed_count,
            (SELECT COUNT(*) FROM likes WHERE from_user = ?) as likes_given,
            (SELECT COUNT(*) FROM likes WHERE to_user = ?) as likes_received,
            (SELECT COUNT(*) FROM mutual_likes WHERE user1 = ? OR user2 = ?) as mutual_count
        FROM users u
        LEFT JOIN profiles p ON u.user_id = p.user_id
        WHERE u.user_id = ?
    ''', (user_id, user_id, user_id, user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        is_premium, views_used, likes_used, profile_views, profile_likes, viewed_count, likes_given, likes_received, mutual_count = stats
        limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
        
        text = (
            f"🍺 Твоя статистика\n\n"
            f"👁 Просмотры:\n"
            f"• Тебя посмотрели: {profile_views}\n"
            f"• Ты посмотрел: {viewed_count}\n"
            f"• Осталось: {limit - views_used}\n\n"
            f"❤️ Лайки:\n"
            f"• Тебя лайкнули: {profile_likes}\n"
            f"• Ты лайкнул: {likes_given}\n"
            f"• Взаимные: {mutual_count}\n"
            f"• Осталось: {limit - likes_used}\n\n"
            f"⭐ Премиум: {'ДА' if is_premium else 'НЕТ'}"
        )
        
        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )

@dp.message(F.text == "⚙️ НАСТРОЙКИ")
async def reply_settings(message: Message, state: FSMContext):
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Уведомления", callback_data="notify_settings")
    builder.button(text="🔐 Приватность", callback_data="privacy")
    builder.button(text="👥 Реферальная система", callback_data="referral")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    builder.adjust(1)
    
    await message.answer(
        "⚙️ Настройки\n\n"
        "Тут можно настроить бота под себя:",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == "❓ ПОМОЩЬ")
async def reply_help(message: Message, state: FSMContext):
    await state.clear()
    
    text = (
        "🍺 Помощь по ПИВЧИКУ\n\n"
        "Как пользоваться:\n"
        "1️⃣ Создай анкету\n"
        "2️⃣ Смотри анкеты других\n"
        "3️⃣ Ставь лайки\n"
        "4️⃣ При взаимном лайке - появится кнопка с именем\n"
        "5️⃣ Нажми на имя чтобы написать в ЛС\n\n"
        "Лимиты:\n"
        f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
        f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
        "Правила:\n"
        "• Без оскорблений\n"
        "• Без спама\n"
        "• Без ссылок в описании\n"
        f"• Возраст {MIN_AGE}+\n\n"
        "По вопросам: @админ"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ГЛАВНОЕ МЕНЮ", callback_data="back_to_main")
    
    await message.answer(
        text,
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == "💰 ПОПОЛНИТЬ")
async def reply_balance(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    text = (
        "💰 ТВОЙ БАЛАНС\n\n"
        f"У тебя: {balance} ⭐\n\n"
        "Способы пополнения:\n"
        "1️⃣ Telegram Stars\n"
        "2️⃣ Криптовалюта (CryptoBot)\n\n"
        "Цены:\n"
        "• 50 ⭐ = 1 день Премиума\n"
        "• 250 ⭐ = 7 дней Премиума\n"
        "• 1000 ⭐ = 30 дней Премиума"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 STARS", callback_data="buy_stars_50")
    builder.button(text="⭐ 250 STARS", callback_data="buy_stars_250")
    builder.button(text="⭐ 1000 STARS", callback_data="buy_stars_1000")
    builder.button(text="₿ КРИПТА", callback_data="buy_crypto")
    builder.button(text="🍺 НАЗАД", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    
    await message.answer(
        text,
        reply_markup=builder.as_markup()
    )

# ========== СТАРТ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    
    cursor = db.conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, joined_date, last_active, balance)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    ''', (
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    db.conn.commit()
    
    welcome_text = (
        "🍺 Добро пожаловать в ПИВЧИК!\n\n"
        "🔥 Здесь люди находят друг друга за кружкой пива\n\n"
        "📌 Что тут есть:\n"
        "• Создай анкету и найди компанию\n"
        "• Смотри анкеты и ставь лайки\n"
        "• При взаимном лайке можно написать в ЛС\n"
        "• Премиум - больше возможностей\n\n"
        "👇 Клавиатура всегда внизу, жми и погнали!"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    await message.answer(
        "🍺 Выбери действие:",
        reply_markup=main_menu(user_id)
    )

# ========== INLINE ОБРАБОТЧИКИ ==========
@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text(
            "❌ У тебя ещё нет анкеты\n"
            "Нажми 🍺 СОЗДАТЬ АНКЕТУ в меню ниже"
        )
        await callback.message.answer(
            "🍺 Главное меню:",
            reply_markup=main_menu(user_id)
        )
        return
    
    await show_my_profile(callback.message, user_id)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message, state)

@dp.callback_query(F.data == "edit_profile_menu")
async def edit_profile_menu_callback(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="🍺 Что хочешь изменить?",
        reply_markup=edit_profile_menu()
    )

@dp.callback_query(F.data == "view_profiles")
async def view_profiles_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await callback.answer("❌ Сначала создай анкету!", show_alert=True)
        return
    
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    is_premium, views_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await callback.message.edit_text(
            f"❌ Лимит просмотров исчерпан ({limit})\nКупи ПРЕМИУМ для увеличения лимита!"
        )
        return
    
    cursor.execute('''
        SELECT p.*, u.username FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id != ? 
        AND p.is_active = 1
        AND p.user_id NOT IN (
            SELECT viewed_user_id FROM views WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    ''', (user_id, user_id))
    
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text(
            "🍺 Ты посмотрел все анкеты! Заходи позже, появятся новые"
        )
        return
    
    cursor.execute('''
        INSERT OR IGNORE INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('''
        UPDATE users SET views_used = views_used + 1 WHERE user_id = ?
    ''', (user_id,))
    
    cursor.execute('''
        UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?
    ''', (profile[1],))
    
    db.conn.commit()
    
    photos = json.loads(profile[7])
    interests = json.loads(profile[8]) if profile[8] else []
    interests_text = ", ".join(interests) if interests else "Не указаны"
    
    text = (
        f"🍺 {profile[2]}, {profile[3]}\n"
        f"⚥ Пол: {profile[4]}\n"
        f"🏙 Город: {profile[5]}\n"
        f"🎯 Интересы: {interests_text}\n\n"
        f"📝 {profile[6]}\n\n"
        f"❤️ Лайков: {profile[11]} | 👁 Просмотров: {profile[10]}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ЛАЙКНУТЬ", callback_data=f"like_{profile[1]}")
    builder.button(text="⏭ ДАЛЬШЕ", callback_data="view_profiles")
    
    if profile[-1]:
        builder.button(text=f"📱 НАПИСАТЬ @{profile[-1]}", url=f"https://t.me/{profile[-1]}")
    
    builder.button(text="⚠️ ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    
    if photos:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photos[0],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "🍺 Наливаем пивчика!\n\n"
        "Давай создадим твою анкету\n\n"
        "Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_name)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя. Максимум 50 символов.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        f"📅 Сколько тебе лет? (от {MIN_AGE} до {MAX_AGE})"
    )
    await state.set_state(ProfileStates.waiting_for_age)

@dp.message(ProfileStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < MIN_AGE or age > MAX_AGE:
            raise ValueError
    except ValueError:
        await message.answer(f"❌ Введи число от {MIN_AGE} до {MAX_AGE}")
        return
    
    await state.update_data(age=age)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍺 Мужской")
    builder.button(text="🍺 Женский")
    builder.button(text="🍺 Другой")
    builder.adjust(2)
    
    await message.answer(
        "👤 Выбери пол:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(ProfileStates.waiting_for_gender)

@dp.message(ProfileStates.waiting_for_gender)
async def process_gender(message: Message, state: FSMContext):
    gender_map = {
        "🍺 Мужской": "Мужской",
        "🍺 Женский": "Женский", 
        "🍺 Другой": "Другой",
        "Мужской": "Мужской",
        "Женский": "Женский",
        "Другой": "Другой"
    }
    
    if message.text not in gender_map:
        await message.answer("❌ Используй кнопки ниже")
        return
    
    await state.update_data(gender=gender_map[message.text])
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_city)

@dp.message(ProfileStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное название города")
        return
    
    await state.update_data(city=message.text)
    await message.answer(
        "📝 Напиши немного о себе\n"
        "Чем занимаешься, что ищешь?\n\n"
        "❌ Ссылки и юзернеймы запрещены!"
    )
    await state.set_state(ProfileStates.waiting_for_about)

@dp.message(ProfileStates.waiting_for_about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://", "vk.com", "instagram.com"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(
            "❌ В описании запрещены ссылки и юзернеймы!\n"
            "Напиши без них"
        )
        return
    
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь минимум {REQUIRED_PHOTOS} фото\n"
        "Можно отправлять по одному",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_photos)
    await state.update_data(photos=[])

@dp.message(ProfileStates.waiting_for_photos, F.photo)
async def process_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    
    await state.update_data(photos=photos)
    
    if len(photos) >= REQUIRED_PHOTOS:
        await show_profile_preview(message, state)
    else:
        await message.answer(
            f"✅ Фото добавлено! Осталось: {REQUIRED_PHOTOS - len(photos)}"
        )

async def show_profile_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    
    preview_text = (
        f"🍺 Превью анкеты\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📅 Возраст: {data['age']}\n"
        f"⚥ Пол: {data['gender']}\n"
        f"🏙 Город: {data['city']}\n"
        f"📝 О себе: {data['about']}\n"
        f"🖼 Фото: {len(data['photos'])} шт.\n\n"
        f"🍺 Всё верно?"
    )
    
    confirm_builder = InlineKeyboardBuilder()
    confirm_builder.button(text="🍺 ДА, СОЗДАТЬ", callback_data="confirm_profile")
    confirm_builder.button(text="✏️ ИСПРАВИТЬ", callback_data="edit_profile")
    
    if data['photos']:
        await message.answer_photo(
            photo=data['photos'][0],
            caption=preview_text,
            reply_markup=confirm_builder.as_markup()
        )
    else:
        await message.answer(
            preview_text,
            reply_markup=confirm_builder.as_markup()
        )

@dp.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    
    photos_json = json.dumps(data['photos'])
    interests_json = json.dumps([])
    
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO profiles 
        (user_id, name, age, gender, city, about, photos, interests, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, data['name'], data['age'], data['gender'],
        data['city'], data['about'], photos_json, interests_json,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    db.conn.commit()
    
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🍺 Анкета создана!\n\n"
        "Теперь можно смотреть анкеты и находить друзей!",
        reply_markup=get_main_keyboard()
    )
    await callback.message.answer(
        "🍺 Главное меню:",
        reply_markup=main_menu(user_id)
    )

@dp.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await create_profile(callback, state)

# ========== ЛАЙКИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer("❌ Нельзя лайкнуть себя!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,))
    user = cursor.fetchone()
    
    is_premium, likes_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит лайков ({limit}) исчерпан!", show_alert=True)
        return
    
    try:
        cursor.execute('''
            INSERT INTO likes (from_user, to_user, created_at)
            VALUES (?, ?, ?)
        ''', (from_user, to_user, datetime.now().isoformat()))
        
        cursor.execute('''
            UPDATE users SET likes_used = likes_used + 1 WHERE user_id = ?
        ''', (from_user,))
        
        cursor.execute('''
            UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?
        ''', (to_user,))
        
        db.conn.commit()
        
        cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user))
        
        if cursor.fetchone():
            cursor.execute('''
                INSERT OR IGNORE INTO mutual_likes (user1, user2, created_at)
                VALUES (?, ?, ?)
            ''', (min(from_user, to_user), max(from_user, to_user), datetime.now().isoformat()))
            
            cursor.execute('''
                UPDATE likes SET is_mutual = 1 
                WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ''', (from_user, to_user, to_user, from_user))
            
            db.conn.commit()
            
            cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (to_user,))
            to_user_data = cursor.fetchone()
            to_username = to_user_data[0]
            to_name = to_user_data[1]
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            profile_name = cursor.fetchone()
            to_profile_name = profile_name[0] if profile_name else to_name
            
            await callback.answer("🍺 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            builder = InlineKeyboardBuilder()
            if to_username:
                builder.button(text=f"📱 НАПИСАТЬ {to_profile_name}", url=f"https://t.me/{to_username}")
            builder.button(text="🍺 ПРОДОЛЖИТЬ", callback_data="view_profiles")
            builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
            builder.adjust(1, 2)
            
            await bot.send_message(
                from_user,
                f"🍺 Взаимный лайк с {to_profile_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder.as_markup()
            )
            
            cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (from_user,))
            from_user_data = cursor.fetchone()
            from_username = from_user_data[0]
            from_name = from_user_data[1]
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_profile_name = cursor.fetchone()
            from_profile_name = from_profile_name[0] if from_profile_name else from_name
            
            builder2 = InlineKeyboardBuilder()
            if from_username:
                builder2.button(text=f"📱 НАПИСАТЬ {from_profile_name}", url=f"https://t.me/{from_username}")
            builder2.button(text="🍺 ПРОДОЛЖИТЬ", callback_data="view_profiles")
            builder2.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
            builder2.adjust(1, 2)
            
            await bot.send_message(
                to_user,
                f"🍺 Взаимный лайк с {from_profile_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder2.as_markup()
            )
            
        else:
            await callback.answer("🍺 Лайк отправлен!")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== ПОКУПКА ЗА ЗВЁЗДЫ ==========
@dp.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars(callback: CallbackQuery):
    amount = int(callback.data.split("_")[2])
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум ПИВЧИК", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="🍺 Премиум ПИВЧИК",
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
    amount = message.successful_payment.total_amount
    
    cursor = db.conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET is_premium = 1,
            premium_until = CASE 
                WHEN premium_until IS NULL THEN ?
                ELSE datetime(premium_until, ?)
            END,
            balance = balance + ?
        WHERE user_id = ?
    ''', (
        (datetime.now() + timedelta(days=days)).isoformat(),
        f'+{days} days',
        amount,
        user_id
    ))
    
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, payment_method, payment_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        amount,
        'stars',
        message.successful_payment.telegram_payment_charge_id,
        'success',
        datetime.now().isoformat()
    ))
    
    db.conn.commit()
    
    await message.answer(
        f"🍺 Оплата прошла успешно!\n\n"
        f"Тебе добавлено {days} дней Премиума!\n"
        f"Баланс пополнен на {amount} ⭐"
    )

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет прав админа")
        return
    
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM profiles')
    total_profiles = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "new"')
    new_complaints = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM mutual_likes')
    mutual_likes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE status = "success"')
    total_donations = cursor.fetchone()[0] or 0
    
    text = (
        "👑 АДМИН ПАНЕЛЬ\n\n"
        f"📊 Статистика:\n"
        f"• 👥 Всего пользователей: {total_users}\n"
        f"• 📝 Всего анкет: {total_profiles}\n"
        f"• ⭐ Премиум: {premium_users}\n"
        f"• ❤️ Взаимных лайков: {mutual_likes}\n"
        f"• 💰 Донатов: {total_donations} ⭐\n\n"
        f"⚠️ Жалоб: {new_complaints}\n\n"
        f"Команды:\n"
        f"/broadcast - рассылка\n"
        f"/complaints - жалобы\n"
        f"/stats - детальная статистика"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 РАССЫЛКА", callback_data="admin_broadcast")
    builder.button(text="⚠️ ЖАЛОБЫ", callback_data="admin_complaints")
    builder.button(text="📊 СТАТИСТИКА", callback_data="admin_stats")
    builder.button(text="🍺 ЗАКРЫТЬ", callback_data="back_to_main")
    builder.adjust(2, 1, 1)
    
    await message.answer(
        text,
        reply_markup=builder.as_markup()
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    print("🍺 ========== ПИВЧИК БОТ ==========")
    print("🍺 Бот запускается...")
    print(f"🍺 Админ: {ADMIN_IDS[0]}")
    print("🍺 База данных: pivchik.db")
    print("🍺 Клавиатура: РАБОТАЕТ")
    print("🍺 Markdown: ВЫКЛЮЧЕН")
    print("🍺 =================================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
