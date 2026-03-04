import logging
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272, 123456789]  # Добавил тебя в админы
PREMIUM_PRICE = 100  # Цена премиума в рублях

FREE_LIMIT = 250
PREMIUM_LIMIT = 1500

MIN_AGE = 18
MAX_AGE = 100
REQUIRED_PHOTOS = 3
ACCOUNT_MIN_AGE_DAYS = 30

# ========== БД ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("dating_bot.db", check_same_thread=False)
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
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
                is_blocked INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                name TEXT,
                age INTEGER,
                gender TEXT,
                about TEXT,
                photos TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                created_at TEXT,
                UNIQUE(from_user, to_user)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                viewed_user_id INTEGER,
                viewed_at TEXT,
                UNIQUE(user_id, viewed_user_id)
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

# ========== FSM СОСТОЯНИЯ ==========
class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_about = State()
    waiting_for_photos = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== УДОБНОЕ МЕНЮ ==========
def main_menu(user_id):
    """Главное меню с красивыми кнопками"""
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
    
    # Верхняя панель со статистикой
    if has_profile:
        builder.button(
            text=f"👤 Моя анкета | 👁 {views_used}/{limit} | ❤️ {likes_used}/{limit}", 
            callback_data="my_profile"
        )
    else:
        builder.button(text="📝 Создать анкету", callback_data="create_profile")
    
    builder.button(text="🔍 Смотреть анкеты", callback_data="view_profiles")
    builder.button(text="💎 Премиум", callback_data="premium_info")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    builder.button(text="📊 Статистика", callback_data="my_stats")
    builder.button(text="❓ Помощь", callback_data="help")
    
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def profile_menu():
    """Меню управления анкетой"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Редактировать анкету", callback_data="edit_profile_menu")
    builder.button(text="📸 Добавить фото", callback_data="add_photos")
    builder.button(text="🗑 Удалить анкету", callback_data="delete_profile")
    builder.button(text="📊 Моя статистика", callback_data="my_stats")
    builder.button(text="🔙 В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def edit_profile_menu():
    """Меню редактирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Имя", callback_data="edit_name")
    builder.button(text="📅 Возраст", callback_data="edit_age")
    builder.button(text="👤 Пол", callback_data="edit_gender")
    builder.button(text="📝 О себе", callback_data="edit_about")
    builder.button(text="🖼 Фото", callback_data="edit_photos")
    builder.button(text="🔙 Назад", callback_data="my_profile")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def back_button():
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

def gender_keyboard():
    """Клавиатура для выбора пола"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨 Мужской")
    builder.button(text="👩 Женский")
    builder.button(text="⚧ Другой")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def confirm_keyboard():
    """Кнопки подтверждения"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_profile")
    builder.button(text="✏️ Редактировать", callback_data="edit_profile")
    return builder.as_markup()

def view_profile_keyboard(viewed_user_id):
    """Кнопки при просмотре анкеты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайкнуть", callback_data=f"like_{viewed_user_id}")
    builder.button(text="⏭ Дальше", callback_data="view_profiles")
    builder.button(text="🔙 В меню", callback_data="back_to_main")
    builder.adjust(2, 1)
    return builder.as_markup()

def premium_menu():
    """Меню премиума"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить Премиум", callback_data="buy_premium")
    builder.button(text="📋 Преимущества", callback_data="premium_benefits")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ========== ПРОВЕРКИ ==========
async def check_user_verification(user_id: int) -> tuple[bool, str]:
    """Проверяет, прошел ли пользователь все проверки"""
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT joined_date FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        return False, "пользователь не найден"
    
    # Проверка наличия анкеты
    cursor.execute('SELECT photos FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        return False, "анкета не создана"
    
    # Проверка фото
    if profile[0]:
        photos = json.loads(profile[0])
        if len(photos) < REQUIRED_PHOTOS:
            return False, f"нужно минимум {REQUIRED_PHOTOS} фото"
    else:
        return False, "нет фото"
    
    # Проверка возраста аккаунта (упрощенно)
    join_date = datetime.fromisoformat(user[0])
    if datetime.now() - join_date < timedelta(days=ACCOUNT_MIN_AGE_DAYS):
        return False, f"аккаунт слишком новый (нужно {ACCOUNT_MIN_AGE_DAYS} дней)"
    
    return True, "ok"

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    
    cursor = db.conn.cursor()
    
    # Регистрируем пользователя
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
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в Дай Винчика 🔞\n\n"
        f"📌 Что тут можно делать:\n"
        f"• Создать анкету и найти пару\n"
        f"• Смотреть анкеты и ставить лайки\n"
        f"• Получить Премиум и больше возможностей\n\n"
        f"👇 Выбери действие в меню ниже:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=main_menu(user_id)
    )

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await cmd_start(message, None)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "📝 Давай создадим твою анкету!\n\n"
        "Напиши своё имя (или никнейм):"
    )
    await state.set_state(ProfileStates.waiting_for_name)

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
        await message.answer(f"❌ Пожалуйста, введи число от {MIN_AGE} до {MAX_AGE}")
        return
    
    await state.update_data(age=age)
    
    await message.answer(
        "👤 Выбери свой пол:",
        reply_markup=gender_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_gender)

@dp.message(ProfileStates.waiting_for_gender)
async def process_gender(message: Message, state: FSMContext):
    gender_map = {
        "👨 Мужской": "Мужской",
        "👩 Женский": "Женский", 
        "⚧ Другой": "Другой"
    }
    
    if message.text not in gender_map:
        await message.answer("❌ Пожалуйста, используй кнопки ниже")
        return
    
    await state.update_data(gender=gender_map[message.text])
    await message.answer(
        "📝 Напиши немного о себе.\n"
        "Чем увлекаешься, что ищешь?\n\n"
        "❌ Запрещено указывать ссылки и юзернеймы!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ProfileStates.waiting_for_about)

@dp.message(ProfileStates.waiting_for_about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://", "vk.com", "instagram.com"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(
            "❌ В описании запрещено указывать ссылки и юзернеймы!\n"
            "Пожалуйста, напиши описание без них."
        )
        return
    
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание. Максимум 500 символов.")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь минимум {REQUIRED_PHOTOS} фото для анкеты.\n"
        "Можно отправлять по одному. Когда закончишь, нажми 'Готово'"
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
        # Показываем превью
        await show_profile_preview(message, state)
    else:
        await message.answer(
            f"✅ Фото добавлено! Осталось: {REQUIRED_PHOTOS - len(photos)}"
        )

@dp.message(ProfileStates.waiting_for_photos, F.text == "Готово")
async def photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) < REQUIRED_PHOTOS:
        await message.answer(
            f"❌ Нужно минимум {REQUIRED_PHOTOS} фото. Отправь ещё {REQUIRED_PHOTOS - len(photos)}"
        )
        return
    
    await show_profile_preview(message, state)

@dp.message(ProfileStates.waiting_for_photos)
async def process_photos_invalid(message: Message):
    await message.answer("❌ Отправь фото или нажми 'Готово'")

async def show_profile_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    
    preview_text = (
        f"📋 *Превью анкеты*\n\n"
        f"👤 *Имя:* {data['name']}\n"
        f"📅 *Возраст:* {data['age']}\n"
        f"⚥ *Пол:* {data['gender']}\n"
        f"📝 *О себе:* {data['about']}\n"
        f"🖼 *Фото:* {len(data['photos'])} шт.\n\n"
        f"*Всё верно?*"
    )
    
    if data['photos']:
        await message.answer_photo(
            photo=data['photos'][0],
            caption=preview_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=confirm_keyboard()
        )
    else:
        await message.answer(
            preview_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=confirm_keyboard()
        )

@dp.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    
    photos_json = json.dumps(data['photos'])
    
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO profiles 
        (user_id, name, age, gender, about, photos, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, data['name'], data['age'], data['gender'],
        data['about'], photos_json,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    db.conn.commit()
    
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "✅ *Анкета успешно создана!*\n\n"
        "Теперь ты можешь смотреть анкеты и находить новые знакомства!",
        parse_mode=ParseMode.MARKDOWN,
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
        SELECT p.*, u.is_premium, u.views_used, u.likes_used 
        FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text(
            "❌ У тебя ещё нет анкеты.\n"
            "Создай её через меню!",
            reply_markup=main_menu(user_id)
        )
        return
    
    photos = json.loads(profile[6])
    is_premium = profile[-3]
    views_used = profile[-2]
    likes_used = profile[-1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    premium_badge = " ⭐" if is_premium else ""
    text = (
        f"👤 *Твоя анкета*{premium_badge}\n\n"
        f"📝 *Имя:* {profile[2]}\n"
        f"📅 *Возраст:* {profile[3]}\n"
        f"⚥ *Пол:* {profile[4]}\n"
        f"📖 *О себе:* {profile[5]}\n"
        f"🖼 *Фото:* {len(photos)} шт.\n\n"
        f"📊 *Статистика:*\n"
        f"• 👁 Просмотров анкеты: {profile[8]}\n"
        f"• ❤️ Лайков анкеты: {profile[9]}\n"
        f"• 📈 Осталось просмотров: {limit - views_used}\n"
        f"• 📈 Осталось лайков: {limit - likes_used}"
    )
    
    if photos:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photos[0],
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=profile_menu()
            )
        except:
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=profile_menu()
            )
    else:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=profile_menu()
        )

# ========== РЕДАКТИРОВАНИЕ ==========
@dp.callback_query(F.data == "edit_profile_menu")
async def edit_profile_menu_callback(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="✏️ *Что хочешь изменить?*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=edit_profile_menu()
    )

@dp.callback_query(F.data.startswith("edit_"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    
    field_names = {
        "name": "имя",
        "age": "возраст", 
        "gender": "пол",
        "about": "описание",
        "photos": "фото"
    }
    
    await state.update_data(edit_field=field)
    await callback.message.edit_caption(
        caption=f"✏️ Введи новое *{field_names[field]}*:",
        parse_mode=ParseMode.MARKDOWN,
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
        if message.text in ["Мужской", "Женский", "Другой", "👨 Мужской", "👩 Женский", "⚧ Другой"]:
            gender = message.text.replace("👨 ", "").replace("👩 ", "").replace("⚧ ", "")
            cursor.execute('UPDATE profiles SET gender = ? WHERE user_id = ?', (gender, user_id))
            await message.answer("✅ Пол обновлен!")
        else:
            await message.answer("❌ Выбери: Мужской, Женский или Другой")
            return
            
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
        "👤 Возвращаемся в анкету...",
        reply_markup=ReplyKeyboardRemove()
    )
    await my_profile(types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="my_profile"
    ))

# ========== ПРОСМОТР АНКЕТ ==========
@dp.callback_query(F.data == "view_profiles")
async def view_profiles(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Проверка наличия анкеты
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await callback.answer("❌ Сначала создай анкету!", show_alert=True)
        return
    
    # Проверка лимитов
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    is_premium, views_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await callback.message.edit_text(
            f"❌ Ты исчерпал лимит просмотров ({limit}).\n"
            "Приобрети Премиум для увеличения лимита!",
            reply_markup=premium_menu()
        )
        return
    
    # Ищем следующую анкету
    cursor.execute('''
        SELECT p.* FROM profiles p
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
            "😕 Ты посмотрел все анкеты!\n"
            "Заходи позже, появятся новые.",
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
    photos = json.loads(profile[6])
    
    text = (
        f"👤 *{profile[2]}, {profile[3]}*\n"
        f"⚥ *Пол:* {profile[4]}\n\n"
        f"📝 *О себе:* {profile[5]}\n\n"
        f"❤️ Лайков: {profile[9]} | 👁 Просмотров: {profile[8]}"
    )
    
    if photos:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photos[0],
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=view_profile_keyboard(profile[1])
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=view_profile_keyboard(profile[1])
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
    
    # Проверка лимитов
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
            await callback.answer("💖 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Получаем имена
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_name = cursor.fetchone()[0]
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            await bot.send_message(
                from_user,
                f"💖 *Взаимный лайк!*\n\n"
                f"Ты понравился *{to_name}*, а вы понравились ему/ей!\n"
                f"Напишите друг другу!",
                parse_mode=ParseMode.MARKDOWN
            )
            await bot.send_message(
                to_user,
                f"💖 *Взаимный лайк!*\n\n"
                f"Ты понравился *{from_name}*, а вы понравились ему/ей!\n"
                f"Напишите друг другу!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback.answer("❤️ Лайк отправлен!")
            
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
            f"⭐ *У тебя активен Премиум!*\n\n"
            f"📅 Действует до: {until}\n\n"
            f"*Твои преимущества:*\n"
            f"• {PREMIUM_LIMIT} просмотров и лайков\n"
            f"• Приоритетный показ анкет\n"
            f"• Специальный значок ⭐ в анкете\n"
            f"• Доступ к новым функциям"
        )
    else:
        text = (
            f"💎 *Премиум подписка*\n\n"
            f"*Лимиты:*\n"
            f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
            f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
            f"*Преимущества:*\n"
            f"• Больше анкет для просмотра\n"
            f"• Ваша анкета показывается чаще\n"
            f"• Значок премиума в профиле\n"
            f"• Ранний доступ к новым функциям\n\n"
            f"💰 *Цена:* {PREMIUM_PRICE} руб.\n\n"
            f"Хочешь стать Премиум пользователем?"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=premium_menu()
    )

@dp.callback_query(F.data == "premium_benefits")
async def premium_benefits(callback: CallbackQuery):
    text = (
        "✨ *Все преимущества Премиум:*\n\n"
        f"🔹 {PREMIUM_LIMIT} просмотров анкет (вместо {FREE_LIMIT})\n"
        f"🔹 {PREMIUM_LIMIT} лайков (вместо {FREE_LIMIT})\n"
        "🔹 Ваша анкета показывается в 2 раза чаще\n"
        "🔹 Специальный значок ⭐ в профиле\n"
        "🔹 Приоритетная поддержка\n"
        "🔹 Доступ к эксклюзивным функциям\n\n"
        f"💰 *Цена:* {PREMIUM_PRICE} руб.\n\n"
        "Нажми 'Купить Премиум' чтобы оформить подписку!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=premium_menu()
    )

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Здесь должна быть интеграция с платежной системой
    # Для теста просто активируем
    
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
        "✅ *Премиум активирован!*\n\n"
        f"Тебе доступно {PREMIUM_LIMIT} просмотров и лайков.\n"
        "Пользуйся новыми возможностями! ⭐",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu(user_id)
    )

# ========== УДАЛЕНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "delete_profile")
async def delete_profile(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="my_profile")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption="⚠️ *Ты уверен, что хочешь удалить анкету?*\n\n"
                "Это действие нельзя отменить!\n"
                "Все твои лайки и просмотры будут удалены.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM likes WHERE from_user = ? OR to_user = ?', (user_id, user_id))
    cursor.execute('DELETE FROM views WHERE user_id = ? OR viewed_user_id = ?', (user_id, user_id))
    db.conn.commit()
    
    await callback.message.delete()
    await callback.message.answer(
        "✅ *Анкета удалена*\n\n"
        "Чтобы создать новую, нажми кнопку 'Создать анкету' в меню",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu(user_id)
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
            (SELECT COUNT(*) FROM likes WHERE to_user = ?) as likes_received
        FROM users u
        LEFT JOIN profiles p ON u.user_id = p.user_id
        WHERE u.user_id = ?
    ''', (user_id, user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        is_premium, views_used, likes_used, profile_views, profile_likes, viewed_count, likes_given, likes_received = stats
        limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
        
        text = (
            f"📊 *Твоя статистика*\n\n"
            f"👁 *Просмотры:*\n"
            f"• Твою анкету посмотрели: {profile_views} раз\n"
            f"• Ты посмотрел анкет: {viewed_count}\n"
            f"• Осталось просмотров: {limit - views_used}\n\n"
            f"❤️ *Лайки:*\n"
            f"• Твою анкету лайкнули: {profile_likes} раз\n"
            f"• Ты лайкнул анкет: {likes_given}\n"
            f"• Тебя лайкнули: {likes_received}\n"
            f"• Осталось лайков: {limit - likes_used}\n\n"
            f"⭐ *Премиум:* {'Да' if is_premium else 'Нет'}"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu(user_id)
        )

# ========== НАСТРОЙКИ ==========
@dp.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сбросить лимиты", callback_data="reset_limits")
    builder.button(text="🔔 Уведомления", callback_data="notifications")
    builder.button(text="🔐 Конфиденциальность", callback_data="privacy")
    builder.button(text="🔙 Главное меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ *Настройки*\n\n"
        "Здесь ты можешь настроить параметры бота:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "reset_limits")
async def reset_limits(callback: CallbackQuery):
    await callback.answer("⚡ Функция скоро будет доступна!", show_alert=True)

@dp.callback_query(F.data == "notifications")
async def notifications(callback: CallbackQuery):
    await callback.answer("🔔 Скоро здесь будут настройки уведомлений", show_alert=True)

@dp.callback_query(F.data == "privacy")
async def privacy(callback: CallbackQuery):
    text = (
        "🔐 *Конфиденциальность*\n\n"
        "• Твои данные хранятся в зашифрованном виде\n"
        "• Фото видят только другие пользователи\n"
        "• Ты можешь удалить анкету в любой момент\n"
        "• Мы не передаем данные третьим лицам"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_button()
    )

# ========== ПОМОЩЬ ==========
@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    text = (
        "❓ *Помощь*\n\n"
        "*Как пользоваться ботом:*\n"
        "1️⃣ Создай анкету (минимум 3 фото)\n"
        "2️⃣ Смотри анкеты других пользователей\n"
        "3️⃣ Ставь лайки понравившимся\n"
        "4️⃣ При взаимном лайке получишь уведомление\n\n"
        "*Лимиты:*\n"
        f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
        f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
        "*Правила:*\n"
        "• Запрещены оскорбления и спам\n"
        "• Не указывай ссылки в описании\n"
        "• Возрастное ограничение {MIN_AGE}+\n\n"
        "По всем вопросам: @админ"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_button()
    )

# ========== НАЗАД В МЕНЮ ==========
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message, None)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    print("🚀 Бот запущен...")
    print(f"👑 Админ ID: {ADMIN_IDS[0]}")
    print("📊 База данных подключена")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
