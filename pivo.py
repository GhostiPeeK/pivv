import logging
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]  # Твой ID

FREE_LIMIT = 250
PREMIUM_LIMIT = 1500
MIN_AGE = 18
MAX_AGE = 100

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
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                likes_used INTEGER DEFAULT 0,
                views_used INTEGER DEFAULT 0,
                joined_date TEXT,
                balance INTEGER DEFAULT 0
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
                photo TEXT,
                created_at TEXT,
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
        
        self.conn.commit()

db = Database()

# ========== FSM СОСТОЯНИЯ ==========
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    about = State()
    photo = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    """Главная клавиатура"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👤 Моя анкета"))
    builder.add(KeyboardButton(text="👀 Смотреть"))
    builder.add(KeyboardButton(text="💎 Премиум"))
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="⚙️ Настройки"))
    builder.add(KeyboardButton(text="❓ Помощь"))
    builder.add(KeyboardButton(text="💰 Баланс"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def back_keyboard():
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="◀️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def gender_keyboard():
    """Клавиатура выбора пола"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👨 Мужской"))
    builder.add(KeyboardButton(text="👩 Женский"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# ========== INLINE МЕНЮ ==========
def main_inline_menu(user_id):
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
        builder.button(text=f"👤 Моя анкета", callback_data="my_profile")
        builder.button(text=f"👀 Смотреть ({limit - views_used})", callback_data="view_profiles")
    else:
        builder.button(text=f"📝 Создать анкету", callback_data="create_profile")
    
    builder.button(text=f"💎 Премиум", callback_data="premium_info")
    builder.button(text=f"📊 Статистика", callback_data="my_stats")
    builder.button(text=f"💰 Баланс: {balance} ⭐", callback_data="balance")
    builder.button(text=f"◀️ Назад", callback_data="back_to_main")
    
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()

def view_profile_keyboard(user_id, username):
    """Кнопки при просмотре анкеты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data=f"like_{user_id}")
    builder.button(text="▶️ Дальше", callback_data="view_profiles")
    if username:
        builder.button(text="📱 Написать", url=f"https://t.me/{username}")
    builder.button(text="◀️ В меню", callback_data="back_to_main")
    builder.adjust(2, 1, 1)
    return builder.as_markup()

# ========== КОМАНДА СТАРТ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Регистрируем пользователя
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, balance)
        VALUES (?, ?, ?, ?, 0)
    ''', (user_id, message.from_user.username, message.from_user.first_name, datetime.now().isoformat()))
    db.conn.commit()
    
    # Отправляем приветствие
    await message.answer(
        f"🍺 Добро пожаловать в ПИВЧИК!\n\n"
        f"🔞 Здесь люди находят друг друга\n\n"
        f"👇 Выбирай в меню:",
        reply_markup=main_keyboard()
    )
    
    # Показываем инлайн меню
    await message.answer(
        "🍺 Главное меню:",
        reply_markup=main_inline_menu(user_id)
    )

# ========== ОБРАБОТЧИКИ REPLY КНОПОК ==========
@dp.message(F.text == "◀️ Назад")
async def back_handler(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

@dp.message(F.text == "👤 Моя анкета")
async def my_profile_handler(message: Message):
    user_id = message.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            "❌ У тебя ещё нет анкеты.\n"
            "Нажми '📝 Создать анкету' в меню:",
            reply_markup=main_keyboard()
        )
        return
    
    # Показываем анкету
    text = (
        f"👤 Твоя анкета\n\n"
        f"Имя: {profile[2]}\n"
        f"Возраст: {profile[3]}\n"
        f"Пол: {profile[4]}\n"
        f"Город: {profile[5]}\n"
        f"О себе: {profile[6]}\n\n"
        f"Просмотров: {profile[9]}\n"
        f"Лайков: {profile[10]}"
    )
    
    if profile[7]:  # если есть фото
        await message.answer_photo(
            photo=profile[7],
            caption=text
        )
    else:
        await message.answer(text)

@dp.message(F.text == "👀 Смотреть")
async def view_handler(message: Message):
    user_id = message.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await message.answer("❌ Сначала создай анкету!")
        return
    
    # Проверяем лимиты
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    is_premium, views_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(f"❌ Лимит просмотров исчерпан ({limit})")
        return
    
    # Ищем анкету
    cursor.execute('''
        SELECT p.*, u.username FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id != ? 
        AND p.user_id NOT IN (
            SELECT viewed_user_id FROM views WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    ''', (user_id, user_id))
    
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer("🍺 Ты посмотрел все анкеты!")
        return
    
    # Сохраняем просмотр
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    db.conn.commit()
    
    # Показываем анкету
    text = (
        f"👤 {profile[2]}, {profile[3]}\n"
        f"🏙 {profile[5]}\n\n"
        f"{profile[6]}\n\n"
        f"❤️ {profile[10]} | 👁 {profile[9]}"
    )
    
    await message.answer_photo(
        photo=profile[7],
        caption=text,
        reply_markup=view_profile_keyboard(profile[1], profile[-1])
    )

@dp.message(F.text == "💎 Премиум")
async def premium_handler(message: Message):
    text = (
        "💎 Премиум ПИВЧИК\n\n"
        f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
        f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
        f"💰 Цена:\n"
        f"• 50 ⭐ = 1 день\n"
        f"• 250 ⭐ = 7 дней\n"
        f"• 1000 ⭐ = 30 дней"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 Stars (1 день)", callback_data="buy_50")
    builder.button(text="⭐ 250 Stars (7 дней)", callback_data="buy_250")
    builder.button(text="⭐ 1000 Stars (30 дней)", callback_data="buy_1000")
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text == "📊 Статистика")
async def stats_handler(message: Message):
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
            (SELECT COUNT(*) FROM likes WHERE from_user = ?) as likes_given
        FROM users u
        LEFT JOIN profiles p ON u.user_id = p.user_id
        WHERE u.user_id = ?
    ''', (user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        text = (
            f"📊 Твоя статистика\n\n"
            f"👁 Тебя посмотрели: {stats[3]}\n"
            f"👁 Ты посмотрел: {stats[5]}\n"
            f"❤️ Тебя лайкнули: {stats[4]}\n"
            f"❤️ Ты лайкнул: {stats[6]}"
        )
        await message.answer(text)

@dp.message(F.text == "⚙️ Настройки")
async def settings_handler(message: Message):
    await message.answer("⚙️ Настройки пока в разработке")

@dp.message(F.text == "❓ Помощь")
async def help_handler(message: Message):
    text = (
        "❓ Помощь\n\n"
        "Как пользоваться:\n"
        "1. Создай анкету\n"
        "2. Смотри анкеты\n"
        "3. Ставь лайки\n"
        "4. При взаимном лайке - общайся\n\n"
        "По вопросам: @admin"
    )
    await message.answer(text)

@dp.message(F.text == "💰 Баланс")
async def balance_handler(message: Message):
    user_id = message.from_user.id
    cursor = db.conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    await message.answer(f"💰 Твой баланс: {balance} ⭐")

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "📝 Создание анкеты\n\n"
        "Как тебя зовут?",
        reply_markup=back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"📅 Сколько тебе лет? (от {MIN_AGE} до {MAX_AGE})",
        reply_markup=back_keyboard()
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
        reply_markup=gender_keyboard()
    )
    await state.set_state(ProfileStates.gender)

@dp.message(ProfileStates.gender)
async def process_gender(message: Message, state: FSMContext):
    if message.text not in ["👨 Мужской", "👩 Женский", "Мужской", "Женский"]:
        await message.answer("❌ Используй кнопки")
        return
    
    gender = "Мужской" if "Мужской" in message.text else "Женский"
    await state.update_data(gender=gender)
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=back_keyboard()
    )
    await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "📝 Напиши о себе",
        reply_markup=back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer(
        "📸 Отправь свое фото",
        reply_markup=back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    # Сохраняем в БД
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO profiles 
        (user_id, name, age, gender, city, about, photo, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        message.from_user.id,
        data['name'],
        data['age'],
        data['gender'],
        data['city'],
        data['about'],
        photo_id,
        datetime.now().isoformat()
    ))
    db.conn.commit()
    
    await state.clear()
    await message.answer(
        "✅ Анкета создана!",
        reply_markup=main_keyboard()
    )

# ========== ЛАЙКИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def like_handler(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    cursor = db.conn.cursor()
    
    # Проверяем лимиты
    cursor.execute('SELECT is_premium, likes_used FROM users WHERE user_id = ?', (from_user,))
    user = cursor.fetchone()
    is_premium, likes_used = user
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer("❌ Лимит лайков исчерпан", show_alert=True)
        return
    
    try:
        cursor.execute('''
            INSERT INTO likes (from_user, to_user, created_at)
            VALUES (?, ?, ?)
        ''', (from_user, to_user, datetime.now().isoformat()))
        
        cursor.execute('UPDATE users SET likes_used = likes_used + 1 WHERE user_id = ?', (from_user,))
        cursor.execute('UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
        db.conn.commit()
        
        # Проверяем взаимность
        cursor.execute('''
            SELECT 1 FROM likes 
            WHERE from_user = ? AND to_user = ?
        ''', (to_user, from_user))
        
        if cursor.fetchone():
            cursor.execute('UPDATE likes SET is_mutual = 1 WHERE from_user IN (?, ?) AND to_user IN (?, ?)',
                         (from_user, to_user, from_user, to_user))
            db.conn.commit()
            
            await callback.answer("❤️ ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Получаем имена
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            await bot.send_message(
                from_user,
                f"❤️ Взаимный лайк с {to_name}!\n"
                f"Теперь вы можете пообщаться!"
            )
        else:
            await callback.answer("❤️ Лайк отправлен!")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== ПОКУПКА ПРЕМИУМА ==========
@dp.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум ПИВЧИК", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💎 Премиум ПИВЧИК",
        description=f"Премиум на {days} дней",
        payload=f"premium_{days}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])
    
    cursor = db.conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET is_premium = 1,
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=days)).isoformat(), user_id))
    db.conn.commit()
    
    await message.answer(f"✅ Премиум активирован на {days} дней!")

# ========== INLINE НАВИГАЦИЯ ==========
@dp.callback_query(F.data == "my_profile")
async def my_profile_inline(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text("❌ Анкета не найдена")
        return
    
    text = f"👤 {profile[2]}, {profile[3]}\n🏙 {profile[5]}\n\n{profile[6]}"
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=profile[7],
        caption=text
    )

@dp.callback_query(F.data == "view_profiles")
async def view_profiles_inline(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.*, u.username FROM profiles p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id != ? 
        AND p.user_id NOT IN (
            SELECT viewed_user_id FROM views WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    ''', (user_id, user_id))
    
    profile = cursor.fetchone()
    
    if not profile:
        await callback.message.edit_text("🍺 Анкет больше нет")
        return
    
    text = f"👤 {profile[2]}, {profile[3]}\n🏙 {profile[5]}\n\n{profile[6]}"
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=profile[7],
        caption=text,
        reply_markup=view_profile_keyboard(profile[1], profile[-1])
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM profiles')
    profiles = cursor.fetchone()[0]
    
    await message.answer(
        f"👑 Админ панель\n\n"
        f"👥 Пользователей: {users}\n"
        f"📝 Анкет: {profiles}"
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🍺 ========== ПИВЧИК ==========")
    print("🍺 Бот запускается...")
    print(f"🍺 Админ: {ADMIN_IDS[0]}")
    print("🍺 =============================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
