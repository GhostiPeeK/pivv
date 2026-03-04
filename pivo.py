import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"  # ВСТАВЬ СВОЙ ТОКЕН
ADMIN_IDS = [2091630272, 1760627021]  # ВСТАВЬ ID АДМИНОВ
PREMIUM_PRICE = 100  # Цена премиума в рублях (для примера)

# Лимиты анкет
FREE_LIMIT = 250
PREMIUM_LIMIT = 1500

# Настройки проверки
MIN_AGE = 18
MAX_AGE = 100
REQUIRED_PHOTOS = 3  # Минимум фото в анкете
ACCOUNT_MIN_AGE_DAYS = 30  # Минимум дней аккаунту

# ========== БД ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("dating_bot.db", check_same_thread=False)
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        # Таблица пользователей
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
                age_confirmed INTEGER DEFAULT 0,
                photo_confirmed INTEGER DEFAULT 0,
                account_confirmed INTEGER DEFAULT 0
            )
        ''')
        # Таблица анкет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                name TEXT,
                age INTEGER,
                gender TEXT,
                about TEXT,
                photos TEXT,  -- JSON массив file_ids
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        # Таблица лайков (для исключения повторных)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                created_at TEXT,
                UNIQUE(from_user, to_user)
            )
        ''')
        # Таблица просмотров
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

# ========== КЛАВИАТУРЫ ==========
def main_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Моя анкета", callback_data="my_profile")
    builder.button(text="🔍 Смотреть анкеты", callback_data="view_profiles")
    builder.button(text="⭐ Премиум", callback_data="premium_info")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    builder.adjust(2)
    return builder.as_markup()

def profile_edit_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Имя", callback_data="edit_name")
    builder.button(text="📅 Возраст", callback_data="edit_age")
    builder.button(text="👤 Пол", callback_data="edit_gender")
    builder.button(text="📝 О себе", callback_data="edit_about")
    builder.button(text="🖼 Фото", callback_data="edit_photos")
    builder.button(text="❌ Удалить анкету", callback_data="delete_profile")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

def gender_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Мужской")
    builder.button(text="Женский")
    builder.button(text="Другой")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_profile")
    builder.button(text="✏️ Редактировать", callback_data="edit_profile")
    return builder.as_markup()

# ========== ПРОВЕРКИ ==========
async def check_user_verification(user_id: int) -> tuple[bool, str]:
    """Проверяет, прошел ли пользователь все проверки"""
    cursor = db.conn.cursor()
    
    # Получаем данные пользователя
    cursor.execute('''
        SELECT age_confirmed, photo_confirmed, account_confirmed, joined_date
        FROM users WHERE user_id = ?
    ''', (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        return False, "Пользователь не найден"
    
    age_conf, photo_conf, acc_conf, joined = user_data
    
    # Проверка возраста
    if not age_conf:
        return False, "возраст"
    
    # Проверка фото (в анкете должно быть минимум фото)
    cursor.execute('SELECT photos FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    if profile and profile[0]:
        import json
        photos = json.loads(profile[0])
        if len(photos) < REQUIRED_PHOTOS:
            return False, "фото (минимум 3)"
    else:
        return False, "фото"
    
    # Проверка аккаунта (возраст аккаунта Telegram)
    if not acc_conf:
        # Здесь должна быть реальная проверка через API, но для примера:
        if joined:
            join_date = datetime.fromisoformat(joined)
            if datetime.now() - join_date < timedelta(days=ACCOUNT_MIN_AGE_DAYS):
                return False, "аккаунт (слишком новый)"
    
    return True, "ok"

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor = db.conn.cursor()
    
    # Регистрируем пользователя если новый
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
    
    # Проверяем есть ли анкета
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if profile:
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n"
            "Используй кнопки ниже для навигации.",
            reply_markup=main_keyboard(user_id)
        )
    else:
        await message.answer(
            "👋 Привет! Я бот знакомств 'Дай Винчика'.\n"
            "Для начала создай свою анкету.\n\n"
            "⚠️ Важно: перед созданием анкеты убедись, что:\n"
            f"• Тебе есть {MIN_AGE} лет\n"
            f"• У тебя есть минимум {REQUIRED_PHOTOS} фото\n"
            f"• Твоему аккаунту больше {ACCOUNT_MIN_AGE_DAYS} дней\n\n"
            "Напиши своё имя (или никнейм):"
        )
        await state.set_state(ProfileStates.waiting_for_name)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("Слишком длинное имя. Максимум 50 символов.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        f"Сколько тебе лет? (от {MIN_AGE} до {MAX_AGE})"
    )
    await state.set_state(ProfileStates.waiting_for_age)

@dp.message(ProfileStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < MIN_AGE or age > MAX_AGE:
            raise ValueError
    except ValueError:
        await message.answer(f"Пожалуйста, введи число от {MIN_AGE} до {MAX_AGE}")
        return
    
    await state.update_data(age=age)
    
    # Подтверждение возраста
    cursor = db.conn.cursor()
    cursor.execute('UPDATE users SET age_confirmed = 1 WHERE user_id = ?', 
                  (message.from_user.id,))
    db.conn.commit()
    
    await message.answer(
        "Выбери свой пол:",
        reply_markup=gender_keyboard()
    )
    await state.set_state(ProfileStates.waiting_for_gender)

@dp.message(ProfileStates.waiting_for_gender)
async def process_gender(message: Message, state: FSMContext):
    gender = message.text
    if gender not in ["Мужской", "Женский", "Другой"]:
        await message.answer("Пожалуйста, используй кнопки ниже")
        return
    
    await state.update_data(gender=gender)
    await message.answer(
        "Напиши немного о себе. Чем увлекаешься, что ищешь?\n"
        "❌ Запрещено указывать ссылки на соцсети!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ProfileStates.waiting_for_about)

@dp.message(ProfileStates.waiting_for_about)
async def process_about(message: Message, state: FSMContext):
    # Проверка на запрещенные ссылки
    forbidden = ["@", "t.me/", "https://", "http://", "vk.com", "instagram.com"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(
            "❌ В описании запрещено указывать ссылки и юзернеймы!\n"
            "Пожалуйста, напиши описание без них."
        )
        return
    
    if len(message.text) > 500:
        await message.answer("Слишком длинное описание. Максимум 500 символов.")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"Отправь минимум {REQUIRED_PHOTOS} фото для анкеты.\n"
        "Можно отправлять по одному."
    )
    await state.set_state(ProfileStates.waiting_for_photos)
    await state.update_data(photos=[])

@dp.message(ProfileStates.waiting_for_photos, F.photo)
async def process_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    # Берем file_id самого большого фото
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    
    await state.update_data(photos=photos)
    
    if len(photos) >= REQUIRED_PHOTOS:
        # Показываем превью анкеты
        await show_profile_preview(message, state)
    else:
        await message.answer(
            f"✅ Фото добавлено! Осталось: {REQUIRED_PHOTOS - len(photos)}"
        )

@dp.message(ProfileStates.waiting_for_photos)
async def process_photos_invalid(message: Message):
    await message.answer("Пожалуйста, отправь фото.")

async def show_profile_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    
    preview_text = (
        f"📋 Превью анкеты:\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📅 Возраст: {data['age']}\n"
        f"⚥ Пол: {data['gender']}\n"
        f"📝 О себе: {data['about']}\n"
        f"🖼 Фото: {len(data['photos'])} шт.\n\n"
        f"Всё верно?"
    )
    
    # Отправляем первое фото как заглавное
    if data['photos']:
        await message.answer_photo(
            photo=data['photos'][0],
            caption=preview_text,
            reply_markup=confirm_keyboard()
        )
    else:
        await message.answer(preview_text, reply_markup=confirm_keyboard())

@dp.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    
    import json
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
    await callback.message.edit_caption(
        caption="✅ Анкета успешно создана!",
        reply_markup=main_keyboard(user_id)
    )

@dp.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_start(callback.message, state)

# ========== ПРОСМОТР АНКЕТ ==========
@dp.callback_query(F.data == "view_profiles")
async def view_profiles(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Проверка лимитов
    cursor = db.conn.cursor()
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    is_premium, views_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await callback.message.edit_text(
            f"❌ Ты исчерпал лимит просмотров ({limit}).\n"
            "Приобрети Премиум для увеличения лимита!",
            reply_markup=premium_keyboard()
        )
        return
    
    # Проверка верификации
    verified, reason = await check_user_verification(user_id)
    if not verified:
        await callback.message.edit_text(
            f"❌ Ты не прошел проверку: {reason}\n"
            "Заполни анкету полностью и убедись, что аккаунт не новый.",
            reply_markup=back_keyboard()
        )
        return
    
    # Ищем следующую непросмотренную анкету
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
            "😕 Больше нет анкет для просмотра.\n"
            "Попробуй позже!",
            reply_markup=back_keyboard()
        )
        return
    
    # Сохраняем просмотр
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    # Обновляем счетчик просмотров
    cursor.execute('''
        UPDATE users SET views_used = views_used + 1 WHERE user_id = ?
    ''', (user_id,))
    
    # Обновляем счетчик просмотров анкеты
    cursor.execute('''
        UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?
    ''', (profile[1],))
    
    db.conn.commit()
    
    # Показываем анкету
    await show_profile(callback.message, profile)

async def show_profile(message: Message, profile_data):
    # profile_data: profile_id, user_id, name, age, gender, about, photos, ...
    import json
    photos = json.loads(profile_data[6])
    
    text = (
        f"👤 {profile_data[2]}, {profile_data[3]}\n"
        f"⚥ {profile_data[4]}\n\n"
        f"📝 {profile_data[5]}\n\n"
        f"❤️ Лайков: {profile_data[9]} | 👁 Просмотров: {profile_data[8]}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data=f"like_{profile_data[1]}")
    builder.button(text="⏭ Далее", callback_data="view_profiles")
    builder.button(text="🔙 В меню", callback_data="back_to_main")
    builder.adjust(2)
    
    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== ЛАЙКИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    cursor = db.conn.cursor()
    
    # Проверка лимитов
    cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,))
    user = cursor.fetchone()
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    is_premium, likes_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит лайков ({limit}) исчерпан!", show_alert=True)
        return
    
    # Сохраняем лайк
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
        
        # Проверяем взаимный лайк
        cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user))
        
        if cursor.fetchone():
            # Взаимный лайк!
            await callback.answer("💖 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Отправляем уведомление обоим
            await bot.send_message(
                from_user,
                f"💖 У вас взаимный лайк! Напиши своему новому знакомому!"
            )
            await bot.send_message(
                to_user,
                f"💖 У вас взаимный лайк! Напиши своему новому знакомому!"
            )
        else:
            await callback.answer("❤️ Лайк отправлен!")
            
    except sqlite3.IntegrityError:
        await callback.answer("Ты уже лайкал эту анкету", show_alert=True)

# ========== ПРЕМИУМ ==========
def premium_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить Премиум", callback_data="buy_premium")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()

@dp.callback_query(F.data == "premium_info")
async def premium_info(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?', 
                  (callback.from_user.id,))
    user = cursor.fetchone()
    
    if user and user[0]:
        until = datetime.fromisoformat(user[1]) if user[1] else "бессрочно"
        text = (
            f"⭐ У тебя активен Премиум!\n"
            f"Действует до: {until}\n\n"
            f"Твои преимущества:\n"
            f"• {PREMIUM_LIMIT} просмотров и лайков (вместо {FREE_LIMIT})\n"
            f"• Приоритетный показ анкет\n"
            f"• Специальный значок в анкете"
        )
    else:
        text = (
            f"💎 Премиум подписка\n\n"
            f"Лимиты:\n"
            f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
            f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
            f"Цена: {PREMIUM_PRICE} руб.\n\n"
            f"После покупки все лимиты увеличатся мгновенно!"
        )
    
    await callback.message.edit_text(text, reply_markup=premium_keyboard())

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    # Здесь должна быть интеграция с платежной системой
    # Для примера просто активируем премиум
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
        "✅ Премиум активирован!\n"
        f"Тебе доступно {PREMIUM_LIMIT} просмотров и лайков.",
        reply_markup=main_keyboard(user_id)
    )

# ========== УПРАВЛЕНИЕ АНКЕТОЙ ==========
@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('''
        SELECT p.*, u.is_premium FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text(
            "У тебя ещё нет анкеты. Создай её через /start",
            reply_markup=back_keyboard()
        )
        return
    
    import json
    photos = json.loads(profile[6])
    
    premium_badge = " ⭐" if profile[-1] else ""
    text = (
        f"👤 Твоя анкета{premium_badge}\n\n"
        f"Имя: {profile[2]}\n"
        f"Возраст: {profile[3]}\n"
        f"Пол: {profile[4]}\n"
        f"О себе: {profile[5]}\n"
        f"Фото: {len(photos)}\n"
        f"Просмотров: {profile[8]}\n"
        f"Лайков: {profile[9]}\n\n"
        f"Статистика:\n"
        f"• Осталось просмотров: ?\n"
        f"• Осталось лайков: ?"
    )
    
    if photos:
        await callback.message.answer_photo(
            photo=photos[0],
            caption=text,
            reply_markup=profile_edit_keyboard()
        )
    else:
        await callback.message.answer(text, reply_markup=profile_edit_keyboard())

@dp.callback_query(F.data == "delete_profile")
async def delete_profile(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="my_profile")
    
    await callback.message.edit_caption(
        caption="⚠️ Ты уверен, что хочешь удалить анкету?\nЭто действие нельзя отменить!",
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
        "✅ Анкета удалена.\n"
        "Чтобы создать новую, используй /start",
        reply_markup=main_keyboard(user_id)
    )

# ========== НАСТРОЙКИ ==========
@dp.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сбросить лимиты", callback_data="reset_limits")
    builder.button(text="📊 Моя статистика", callback_data="my_stats")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ Настройки",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('''
        SELECT 
            (SELECT COUNT(*) FROM views WHERE viewed_user_id = ?) as profile_views,
            (SELECT COUNT(*) FROM likes WHERE to_user = ?) as profile_likes,
            u.views_used, u.likes_used, u.is_premium
        FROM users u WHERE u.user_id = ?
    ''', (user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        profile_views, profile_likes, views_used, likes_used, is_premium = stats
        limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
        
        text = (
            f"📊 Твоя статистика:\n\n"
            f"👁 Просмотров анкеты: {profile_views}\n"
            f"❤️ Лайков анкеты: {profile_likes}\n"
            f"📈 Использовано просмотров: {views_used}/{limit}\n"
            f"📈 Использовано лайков: {likes_used}/{limit}\n"
            f"⭐ Премиум: {'Да' if is_premium else 'Нет'}"
        )
        
        await callback.message.edit_text(text, reply_markup=back_keyboard())

@dp.callback_query(F.data == "reset_limits")
async def reset_limits(callback: CallbackQuery):
    # Только для админов или по подписке
    await callback.answer("Эта функция временно недоступна", show_alert=True)

# ========== ОБЩИЕ КНОПКИ ==========
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message, None)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
