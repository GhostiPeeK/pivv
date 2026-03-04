import logging
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
import random
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]  # Твой ID

PREMIUM_PRICE = 100  # рублей
FREE_LIMIT = 250
PREMIUM_LIMIT = 1500

MIN_AGE = 18
MAX_AGE = 100
REQUIRED_PHOTOS = 3
ACCOUNT_MIN_AGE_DAYS = 30

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
                referred_by INTEGER
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
                created_at TEXT
            )
        ''')
        
        # Взаимные лайки (пары)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutual_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 INTEGER,
                user2 INTEGER,
                created_at TEXT,
                UNIQUE(user1, user2)
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

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== УДОБНАЯ REPLY КЛАВИАТУРА (ВСЕГДА ВНИЗУ) ==========
def get_main_keyboard():
    """Главная клавиатура которая всегда внизу"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🍺 МОЯ АНКЕТА"))
    builder.add(KeyboardButton(text="👀 СМОТРЕТЬ"))
    builder.add(KeyboardButton(text="⭐ ПРЕМИУМ"))
    builder.add(KeyboardButton(text="📊 СТАТИСТИКА"))
    builder.add(KeyboardButton(text="⚙️ НАСТРОЙКИ"))
    builder.add(KeyboardButton(text="❓ ПОМОЩЬ"))
    builder.adjust(2, 2, 2)  # 3 ряда по 2 кнопки
    return builder.as_markup(resize_keyboard=True)

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🍺 ГЛАВНОЕ МЕНЮ"))
    return builder.as_markup(resize_keyboard=True)

# ========== INLINE МЕНЮ ==========
def main_menu(user_id):
    """Инлайн меню (дополнительное)"""
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.profile_id, u.is_premium, u.views_used, u.likes_used 
        FROM users u 
        LEFT JOIN profiles p ON u.user_id = p.user_id 
        WHERE u.user_id = ?
    ''', (user_id,))
    data = cursor.fetchone()
    
    has_profile = data and data[0] is not None
    is_premium = data[1] if data else False
    views_used = data[2] if data else 0
    likes_used = data[3] if data else 0
    
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    builder = InlineKeyboardBuilder()
    
    if has_profile:
        builder.button(text=f"👤 МОЯ АНКЕТА", callback_data="my_profile")
        builder.button(text=f"👀 СМОТРЕТЬ ({limit - views_used} ост.)", callback_data="view_profiles")
    else:
        builder.button(text="🍺 СОЗДАТЬ АНКЕТУ", callback_data="create_profile")
    
    builder.button(text="⭐ ПРЕМИУМ", callback_data="premium_info")
    builder.button(text="📊 СТАТИСТИКА", callback_data="my_stats")
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

def view_profile_keyboard(viewed_user_id, viewed_name, viewed_username):
    """Кнопки при просмотре анкеты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ЛАЙКНУТЬ", callback_data=f"like_{viewed_user_id}")
    builder.button(text="⏭ ДАЛЬШЕ", callback_data="view_profiles")
    
    # Если есть username, добавляем кнопку перехода в ЛС
    if viewed_username:
        builder.button(text=f"📱 НАПИСАТЬ @{viewed_username}", url=f"https://t.me/{viewed_username}")
    
    builder.button(text="⚠️ ПОЖАЛОВАТЬСЯ", callback_data=f"complaint_{viewed_user_id}")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()

def mutual_like_keyboard(user_id, username, name):
    """Кнопки при взаимном лайке"""
    builder = InlineKeyboardBuilder()
    if username:
        builder.button(text=f"📱 НАПИСАТЬ {name}", url=f"https://t.me/{username}")
    else:
        builder.button(text=f"📱 НЕТ USERNAME", callback_data="no_username")
    builder.button(text="🍺 ПРОДОЛЖИТЬ", callback_data="view_profiles")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    builder.adjust(1, 2)
    return builder.as_markup()

def premium_menu():
    """Меню премиума"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 КУПИТЬ ПРЕМИУМ", callback_data="buy_premium")
    builder.button(text="🎁 БОНУСЫ", callback_data="premium_benefits")
    builder.button(text="🍺 НАЗАД", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def interests_keyboard():
    """Клавиатура интересов"""
    interests = [
        "🍺 Пиво", "🎵 Музыка", "🎮 Игры", "🏋️ Спорт",
        "🎬 Кино", "📚 Книги", "🍽 Готовка", "✈️ Путешествия",
        "🐱 Животные", "🎨 Рисование", "💻 IT", "🚗 Тачки"
    ]
    builder = InlineKeyboardBuilder()
    for interest in interests:
        builder.button(text=interest, callback_data=f"interest_{interest}")
    builder.button(text="🍺 ГОТОВО", callback_data="interests_done")
    builder.adjust(3)
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ REPLY КЛАВИАТУРЫ ==========
@dp.message(F.text == "🍺 ГЛАВНОЕ МЕНЮ")
async def reply_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

@dp.message(F.text == "🍺 МОЯ АНКЕТА")
async def reply_my_profile(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="my_profile"
    )
    await my_profile(callback)

@dp.message(F.text == "👀 СМОТРЕТЬ")
async def reply_view_profiles(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="view_profiles"
    )
    await view_profiles(callback)

@dp.message(F.text == "⭐ ПРЕМИУМ")
async def reply_premium(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="premium_info"
    )
    await premium_info(callback)

@dp.message(F.text == "📊 СТАТИСТИКА")
async def reply_stats(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="my_stats"
    )
    await my_stats(callback)

@dp.message(F.text == "⚙️ НАСТРОЙКИ")
async def reply_settings(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="settings"
    )
    await settings_menu(callback)

@dp.message(F.text == "❓ ПОМОЩЬ")
async def reply_help(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="help"
    )
    await help_menu(callback)

# ========== СТАРТ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    
    cursor = db.conn.cursor()
    
    # Регистрация
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, joined_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    db.conn.commit()
    
    # Приветствие
    welcome_text = (
        "🍺 *Добро пожаловать в ПИВЧИК\\!*\n\n"
        "🔥 *Здесь люди находят друг друга за кружкой пива*\n\n"
        "📌 *Что тут есть:*\n"
        "• Создай анкету и найди компанию\n"
        "• Смотри анкеты и ставь лайки\n"
        "• При взаимном лайке можно написать в ЛС\n"
        "• Премиум \- больше возможностей\n\n"
        "👇 *Клавиатура всегда внизу, жми и погнали\\!*"
    )
    
    await message.answer(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_keyboard()  # Удобная клавиатура внизу
    )
    
    # Дополнительно показываем инлайн меню
    await message.answer(
        "🍺 *Выбери действие:*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(user_id)
    )

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "🍺 *Наливаем пивчика\\!*\n\n"
        "Давай создадим твою анкету\n\n"
        "Как тебя зовут\\?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_name)

@dp.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя\\. Максимум 50 символов\\.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        f"📅 *Сколько тебе лет\\?* \\(от {MIN_AGE} до {MAX_AGE}\\)",
        parse_mode=ParseMode.MARKDOWN_V2
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
    
    # Клавиатура для пола
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍺 Мужской")
    builder.button(text="🍺 Женский")
    builder.button(text="🍺 Другой")
    builder.adjust(2)
    
    await message.answer(
        "👤 *Выбери пол:*",
        parse_mode=ParseMode.MARKDOWN_V2,
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
        "🏙 *Из какого ты города\\?*",
        parse_mode=ParseMode.MARKDOWN_V2,
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
        "📝 *Напиши немного о себе*\n"
        "Чем занимаешься, что ищешь\\?\n\n"
        "❌ Ссылки и юзернеймы запрещены\\!",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    await state.set_state(ProfileStates.waiting_for_about)

@dp.message(ProfileStates.waiting_for_about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://", "vk.com", "instagram.com"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(
            "❌ В описании запрещены ссылки и юзернеймы\\!\n"
            "Напиши без них"
        )
        return
    
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание\\. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"🎯 *Выбери свои интересы*\n"
        f"Можно выбрать несколько",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=interests_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_interests)
    await state.update_data(interests=[])

@dp.callback_query(ProfileStates.waiting_for_interests, F.data.startswith("interest_"))
async def process_interest(callback: CallbackQuery, state: FSMContext):
    interest = callback.data.replace("interest_", "")
    data = await state.get_data()
    interests = data.get("interests", [])
    
    if interest in interests:
        interests.remove(interest)
        await callback.answer(f"❌ Убрано: {interest}")
    else:
        interests.append(interest)
        await callback.answer(f"✅ Добавлено: {interest}")
    
    await state.update_data(interests=interests)

@dp.callback_query(ProfileStates.waiting_for_interests, F.data == "interests_done")
async def interests_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    interests = data.get("interests", [])
    
    if len(interests) < 1:
        await callback.answer("❌ Выбери хотя бы один интерес!", show_alert=True)
        return
    
    await callback.message.delete()
    await callback.message.answer(
        f"📸 *Отправь минимум {REQUIRED_PHOTOS} фото*\n"
        "Можно отправлять по одному",
        parse_mode=ParseMode.MARKDOWN_V2,
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
            f"✅ Фото добавлено\\! Осталось: {REQUIRED_PHOTOS - len(photos)}"
        )

async def show_profile_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    interests = ", ".join(data.get("interests", []))
    
    preview_text = (
        f"🍺 *Превью анкеты*\n\n"
        f"👤 *Имя:* {data['name']}\n"
        f"📅 *Возраст:* {data['age']}\n"
        f"⚥ *Пол:* {data['gender']}\n"
        f"🏙 *Город:* {data['city']}\n"
        f"📝 *О себе:* {data['about']}\n"
        f"🎯 *Интересы:* {interests}\n"
        f"🖼 *Фото:* {len(data['photos'])} шт\\.\n\n"
        f"🍺 *Всё верно\\?*"
    )
    
    confirm_builder = InlineKeyboardBuilder()
    confirm_builder.button(text="🍺 ДА, СОЗДАТЬ", callback_data="confirm_profile")
    confirm_builder.button(text="✏️ ИСПРАВИТЬ", callback_data="edit_profile")
    
    if data['photos']:
        await message.answer_photo(
            photo=data['photos'][0],
            caption=preview_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=confirm_builder.as_markup()
        )
    else:
        await message.answer(
            preview_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=confirm_builder.as_markup()
        )

@dp.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    
    photos_json = json.dumps(data['photos'])
    interests_json = json.dumps(data.get('interests', []))
    
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
        "🍺 *Анкета создана\\!*\n\n"
        "Теперь можно смотреть анкеты и находить друзей\\!",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_keyboard()
    )
    await callback.message.answer(
        "🍺 *Главное меню:*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(user_id)
    )

@dp.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await create_profile(callback, state)

# ========== МОЯ АНКЕТА ==========
@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('''
        SELECT p.*, u.is_premium, u.views_used, u.likes_used, u.username
        FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text(
            "❌ *У тебя ещё нет анкеты*\n"
            "Нажми 🍺 *СОЗДАТЬ АНКЕТУ*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(user_id)
        )
        return
    
    photos = json.loads(profile[7])  # photos
    interests = json.loads(profile[8]) if profile[8] else []
    is_premium = profile[-4]
    views_used = profile[-3]
    likes_used = profile[-2]
    username = profile[-1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    premium_badge = " ⭐" if is_premium else ""
    interests_text = ", ".join(interests) if interests else "Не указаны"
    
    text = (
        f"🍺 *Твоя анкета*{premium_badge}\n\n"
        f"👤 *Имя:* {profile[2]}\n"
        f"📅 *Возраст:* {profile[3]}\n"
        f"⚥ *Пол:* {profile[4]}\n"
        f"🏙 *Город:* {profile[5]}\n"
        f"📝 *О себе:* {profile[6]}\n"
        f"🎯 *Интересы:* {interests_text}\n"
        f"🖼 *Фото:* {len(photos)} шт\\.\n"
        f"📱 *Username:* @{username if username else 'нет'}\n\n"
        f"📊 *Статистика:*\n"
        f"• 👁 Просмотров: {profile[11]}\n"
        f"• ❤️ Лайков: {profile[12]}\n"
        f"• 📈 Осталось просмотров: {limit - views_used}\n"
        f"• 📈 Осталось лайков: {limit - likes_used}"
    )
    
    if photos:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photos[0],
                caption=text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=profile_menu()
            )
        except:
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=profile_menu()
            )
    else:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=profile_menu()
        )

# ========== ПРОСМОТР АНКЕТ ==========
@dp.callback_query(F.data == "view_profiles")
async def view_profiles(callback: CallbackQuery):
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
            f"❌ *Лимит просмотров исчерпан* \\({limit}\\)\n"
            "Купи 🍺 *ПРЕМИУМ* для увеличения лимита\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=premium_menu()
        )
        return
    
    # Ищем анкету
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
            "🍺 *Ты посмотрел все анкеты\\!*\n"
            "Заходи позже, появятся новые",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(user_id)
        )
        return
    
    # Сохраняем просмотр
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
    
    # Показываем анкету
    photos = json.loads(profile[7])
    interests = json.loads(profile[8]) if profile[8] else []
    interests_text = ", ".join(interests) if interests else "Не указаны"
    
    text = (
        f"🍺 *{profile[2]}, {profile[3]}*\n"
        f"⚥ *Пол:* {profile[4]}\n"
        f"🏙 *Город:* {profile[5]}\n"
        f"🎯 *Интересы:* {interests_text}\n\n"
        f"📝 *О себе:* {profile[6]}\n\n"
        f"❤️ Лайков: {profile[11]} | 👁 Просмотров: {profile[10]}"
    )
    
    if photos:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photos[0],
            caption=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=view_profile_keyboard(profile[1], profile[2], profile[-1])  # передаем username
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=view_profile_keyboard(profile[1], profile[2], profile[-1])
        )

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
        
        # Проверка взаимности
        cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user))
        
        if cursor.fetchone():
            # Взаимный лайк!
            # Сохраняем в таблицу mutual_likes
            cursor.execute('''
                INSERT OR IGNORE INTO mutual_likes (user1, user2, created_at)
                VALUES (?, ?, ?)
            ''', (min(from_user, to_user), max(from_user, to_user), datetime.now().isoformat()))
            
            # Обновляем статус у обоих лайков
            cursor.execute('''
                UPDATE likes SET is_mutual = 1 
                WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ''', (from_user, to_user, to_user, from_user))
            
            db.conn.commit()
            
            # Получаем информацию о пользователе
            cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (to_user,))
            to_user_data = cursor.fetchone()
            to_username = to_user_data[0]
            to_name = to_user_data[1]
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            profile_name = cursor.fetchone()
            to_profile_name = profile_name[0] if profile_name else to_name
            
            await callback.answer("🍺 ВЗАИМНЫЙ ЛАЙК! Можете написать друг другу!", show_alert=True)
            
            # Уведомление для того кто лайкнул
            await bot.send_message(
                from_user,
                f"🍺 *Взаимный лайк\\!*\n\n"
                f"Ты понравился *{to_profile_name}*\n"
                f"Теперь вы можете пообщаться\\!",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=mutual_like_keyboard(to_user, to_username, to_profile_name)
            )
            
            # Получаем информацию о том кто лайкнул
            cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (from_user,))
            from_user_data = cursor.fetchone()
            from_username = from_user_data[0]
            from_name = from_user_data[1]
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_profile_name = cursor.fetchone()
            from_profile_name = from_profile_name[0] if from_profile_name else from_name
            
            # Уведомление для того кого лайкнули
            await bot.send_message(
                to_user,
                f"🍺 *Взаимный лайк\\!*\n\n"
                f"Ты понравился *{from_profile_name}*\n"
                f"Теперь вы можете пообщаться\\!",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=mutual_like_keyboard(from_user, from_username, from_profile_name)
            )
            
        else:
            await callback.answer("🍺 Лайк отправлен!")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== ПРЕМИУМ ==========
@dp.callback_query(F.data == "premium_info")
async def premium_info(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?', 
                  (callback.from_user.id,))
    user = cursor.fetchone()
    
    if user and user[0]:
        until = datetime.fromisoformat(user[1]).strftime("%d.%m.%Y") if user[1] else "бессрочно"
        text = (
            f"🍺 *У тебя ПРЕМИУМ\\!*\n\n"
            f"📅 Действует до: {until}\n\n"
            f"*Твои бонусы:*\n"
            f"• 🍺 {PREMIUM_LIMIT} просмотров\n"
            f"• 🍺 {PREMIUM_LIMIT} лайков\n"
            f"• ⭐ Значок в анкете\n"
            f"• 🔥 Показ в топе"
        )
    else:
        text = (
            f"🍺 *ПРЕМИУМ*\n\n"
            f"*Лимиты:*\n"
            f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
            f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
            f"*Бонусы:*\n"
            f"• 🍺 Больше анкет\n"
            f"• ⭐ Значок в профиле\n"
            f"• 🔥 Показ в топе\n\n"
            f"💰 *Цена:* {PREMIUM_PRICE} руб\\.\n\n"
            f"Хочешь больше возможностей\\?"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=premium_menu()
    )

@dp.callback_query(F.data == "premium_benefits")
async def premium_benefits(callback: CallbackQuery):
    text = (
        "🍺 *Все бонусы ПРЕМИУМ:*\n\n"
        f"🔹 {PREMIUM_LIMIT} просмотров \\(вместо {FREE_LIMIT}\\)\n"
        f"🔹 {PREMIUM_LIMIT} лайков \\(вместо {FREE_LIMIT}\\)\n"
        "🔹 Ваша анкета показывается чаще\n"
        "🔹 Специальный значок ⭐\n"
        "🔹 Приоритетная поддержка\n\n"
        f"💰 *Цена:* {PREMIUM_PRICE} руб\\.\n\n"
        "Нажми 🍺 *КУПИТЬ ПРЕМИУМ* чтобы оформить\\!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=premium_menu()
    )

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET is_premium = 1, 
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=30)).isoformat(), user_id))
    db.conn.commit()
    
    await callback.message.edit_text(
        "🍺 *ПРЕМИУМ АКТИВИРОВАН\\!*\n\n"
        f"Теперь у тебя {PREMIUM_LIMIT} просмотров и лайков\n"
        "Пользуйся новыми возможностями ⭐",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(user_id)
    )

# ========== РЕДАКТИРОВАНИЕ ==========
@dp.callback_query(F.data == "edit_profile_menu")
async def edit_profile_menu_callback(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="🍺 *Что хочешь изменить\\?*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=edit_profile_menu()
    )

@dp.callback_query(F.data.startswith("edit_"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    
    field_names = {
        "name": "имя",
        "age": "возраст", 
        "gender": "пол",
        "city": "город",
        "about": "описание",
        "interests": "интересы",
        "photos": "фото"
    }
    
    if field == "interests":
        await callback.message.edit_caption(
            caption="🎯 *Выбери новые интересы*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=interests_keyboard()
        )
        await state.set_state(ProfileStates.waiting_for_interests)
        await state.update_data(interests=[])
        return
    
    await state.update_data(edit_field=field)
    await callback.message.edit_caption(
        caption=f"✏️ Введи новое *{field_names[field]}*:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_button()
    )
    await state.set_state(ProfileStates.waiting_for_edit_value)

@dp.message(ProfileStates.waiting_for_edit_value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    
    if field == "name":
        cursor.execute('UPDATE profiles SET name = ? WHERE user_id = ?', (message.text, user_id))
        await message.answer("✅ Имя обновлено!")
        
    elif field == "age":
        try:
            age = int(message.text)
            if MIN_AGE <= age <= MAX_AGE:
                cursor.execute('UPDATE profiles SET age = ? WHERE user_id = ?', (age, user_id))
                await message.answer("✅ Возраст обновлен!")
            else:
                await message.answer(f"❌ Возраст должен быть от {MIN_AGE} до {MAX_AGE}")
                return
        except:
            await message.answer("❌ Введи число")
            return
            
    elif field == "gender":
        if message.text in ["Мужской", "Женский", "Другой"]:
            cursor.execute('UPDATE profiles SET gender = ? WHERE user_id = ?', (message.text, user_id))
            await message.answer("✅ Пол обновлен!")
        else:
            await message.answer("❌ Выбери: Мужской, Женский или Другой")
            return
            
    elif field == "city":
        cursor.execute('UPDATE profiles SET city = ? WHERE user_id = ?', (message.text, user_id))
        await message.answer("✅ Город обновлен!")
            
    elif field == "about":
        if len(message.text) <= 500:
            cursor.execute('UPDATE profiles SET about = ? WHERE user_id = ?', (message.text, user_id))
            await message.answer("✅ Описание обновлено!")
        else:
            await message.answer("❌ Максимум 500 символов")
            return
    
    db.conn.commit()
    await state.clear()
    await message.answer(
        "🍺 Возвращаемся в анкету...",
        reply_markup=get_main_keyboard()
    )
    await my_profile(types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="my_profile"
    ))

# ========== УДАЛЕНИЕ ==========
@dp.callback_query(F.data == "delete_profile")
async def delete_profile(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ДА, УДАЛИТЬ", callback_data="confirm_delete")
    builder.button(text="❌ ОТМЕНА", callback_data="my_profile")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption="⚠️ *Ты точно хочешь удалить анкету\\?*\n\n"
                "Это действие нельзя отменить\\!\n"
                "Все лайки и просмотры пропадут",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM likes WHERE from_user = ? OR to_user = ?', (user_id, user_id))
    cursor.execute('DELETE FROM views WHERE user_id = ? OR viewed_user_id = ?', (user_id, user_id))
    cursor.execute('DELETE FROM mutual_likes WHERE user1 = ? OR user2 = ?', (user_id, user_id))
    db.conn.commit()
    
    await callback.message.delete()
    await callback.message.answer(
        "🍺 *Анкета удалена*\n\n"
        "Чтобы создать новую, нажми 🍺 *СОЗДАТЬ АНКЕТУ*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_keyboard()
    )

# ========== СТАТИСТИКА ==========
@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
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
            f"🍺 *Твоя статистика*\n\n"
            f"👁 *Просмотры:*\n"
            f"• Тебя посмотрели: {profile_views}\n"
            f"• Ты посмотрел: {viewed_count}\n"
            f"• Осталось: {limit - views_used}\n\n"
            f"❤️ *Лайки:*\n"
            f"• Тебя лайкнули: {profile_likes}\n"
            f"• Ты лайкнул: {likes_given}\n"
            f"• Взаимные: {mutual_count}\n"
            f"• Осталось: {limit - likes_used}\n\n"
            f"⭐ *Премиум:* {'ДА' if is_premium else 'НЕТ'}"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(user_id)
        )

# ========== ЖАЛОБЫ ==========
@dp.callback_query(F.data.startswith("complaint_"))
async def complaint_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(complaint_user=user_id)
    
    builder = InlineKeyboardBuilder()
    reasons = ["Спам", "Оскорбления", "18+ контент", "Фейк", "Другое"]
    for reason in reasons:
        builder.button(text=reason, callback_data=f"complaint_reason_{reason}")
    builder.button(text="❌ Отмена", callback_data="back_to_main")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption="⚠️ *Выбери причину жалобы:*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=builder.as_markup()
    )
    await state.set_state(ProfileStates.waiting_for_complaint)

@dp.callback_query(ProfileStates.waiting_for_complaint, F.data.startswith("complaint_reason_"))
async def process_complaint(callback: CallbackQuery, state: FSMContext):
    reason = callback.data.replace("complaint_reason_", "")
    data = await state.get_data()
    on_user = data.get("complaint_user")
    
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (from_user, on_user, reason, created_at)
        VALUES (?, ?, ?, ?)
    ''', (callback.from_user.id, on_user, reason, datetime.now().isoformat()))
    db.conn.commit()
    
    await state.clear()
    await callback.answer("✅ Жалоба отправлена админу!", show_alert=True)
    await callback.message.delete()
    await cmd_start(callback.message, None)

# ========== НАСТРОЙКИ ==========
@dp.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Уведомления", callback_data="notify_settings")
    builder.button(text="🔐 Приватность", callback_data="privacy")
    builder.button(text="👥 Реферальная система", callback_data="referral")
    builder.button(text="🍺 В меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ *Настройки*\n\n"
        "Тут можно настроить бота под себя:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "notify_settings")
async def notify_settings(callback: CallbackQuery):
    await callback.answer("🔔 Скоро тут будут настройки уведомлений", show_alert=True)

@dp.callback_query(F.data == "privacy")
async def privacy(callback: CallbackQuery):
    text = (
        "🔐 *Приватность*\n\n"
        "• Твои данные в безопасности\n"
        "• Фото видят только пользователи\n"
        "• Можно удалить анкету в любой момент\n"
        "• Мы не передаем данные третьим лицам\n"
        "• Жалобы рассматриваются админом"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_button()
    )

@dp.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT referral_count FROM users WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    
    text = (
        "👥 *Реферальная система*\n\n"
        f"Приглашай друзей и получай бонусы\\!\n\n"
        f"• Ты пригласил: {count} чел\\.\n"
        f"• За каждого друга \\+10 просмотров\n\n"
        f"*Твоя ссылка:*\n"
        f"`{link}`"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_button()
    )

# ========== ПОМОЩЬ ==========
@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    text = (
        "🍺 *Помощь по ПИВЧИКУ*\n\n"
        "*Как пользоваться:*\n"
        "1️⃣ Создай анкету\n"
        "2️⃣ Смотри анкеты других\n"
        "3️⃣ Ставь лайки\n"
        "4️⃣ При взаимном лайке - появится кнопка с именем\n"
        "5️⃣ Нажми на имя чтобы написать в ЛС\n\n"
        "*Лимиты:*\n"
        f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
        f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
        "*Правила:*\n"
        "• Без оскорблений\n"
        "• Без спама\n"
        "• Без ссылок в описании\n"
        f"• Возраст {MIN_AGE}\\+\n\n"
        "*По вопросам:* @админ"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_button()
    )

# ========== НАЗАД ==========
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message, None)

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
    
    cursor.execute('SELECT COUNT(*) FROM complaints')
    total_complaints = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM mutual_likes')
    mutual_likes = cursor.fetchone()[0]
    
    text = (
        "👑 *Админ панель*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📝 Всего анкет: {total_profiles}\n"
        f"❤️ Взаимных лайков: {mutual_likes}\n"
        f"⚠️ Жалоб: {total_complaints}\n\n"
        "Команды:\n"
        "/broadcast - рассылка\n"
        "/stats - полная статистика"
    )
    
    await message.answer(text, parse_mode=ParseMode.MARKDOWN_V2)

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
    print("🍺 Клавиатура: ВКЛЮЧЕНА")
    print("🍺 =================================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
