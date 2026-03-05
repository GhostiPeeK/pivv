import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

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
        likes_count INTEGER DEFAULT 0
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
conn.commit()

# ========== FSM ==========
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    about = State()
    photo = State()

class ComplaintStates(StatesGroup):
    reason = State()

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Главная клавиатура"""
    kb = [
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="👀 Смотреть")],
        [KeyboardButton(text="💎 Премиум"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь")],
        [KeyboardButton(text="💰 Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    kb = [[KeyboardButton(text="◀️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    """Клавиатура выбора пола"""
    kb = [
        [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Регистрируем пользователя
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, balance)
        VALUES (?, ?, ?, ?, 0)
    ''', (user_id, message.from_user.username, message.from_user.first_name, datetime.now().isoformat()))
    conn.commit()
    
    # Приветствие
    await message.answer(
        f"🍺 ДОБРО ПОЖАЛОВАТЬ В ПИВЧИК!\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"🔞 Здесь люди находят друг друга\n\n"
        f"👇 Выбирай в меню:",
        reply_markup=get_main_keyboard()
    )

# ========== МОЯ АНКЕТА ==========
@dp.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            "❌ У тебя ещё нет анкеты!\n"
            "Нажми /create чтобы создать анкету"
        )
        return
    
    # Получаем статистику
    cursor.execute('SELECT COUNT(*) FROM views WHERE viewed_user_id = ?', (user_id,))
    views = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM likes WHERE to_user = ?', (user_id,))
    likes = cursor.fetchone()[0]
    
    text = (
        f"👤 ТВОЯ АНКЕТА\n\n"
        f"Имя: {profile[2]}\n"
        f"Возраст: {profile[3]}\n"
        f"Пол: {profile[4]}\n"
        f"Город: {profile[5]}\n"
        f"О себе: {profile[6]}\n\n"
        f"Просмотров: {views}\n"
        f"Лайков: {likes}"
    )
    
    # Создаем инлайн кнопки для управления анкетой
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data="edit_profile")
    builder.button(text="📸 Изменить фото", callback_data="edit_photo")
    builder.button(text="🗑 Удалить", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if profile[7]:  # если есть фото
        await message.answer_photo(
            photo=profile[7],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    await message.answer(
        "📝 СОЗДАНИЕ АНКЕТЫ\n\n"
        "Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя. Максимум 50 символов.")
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

@dp.message(ProfileStates.gender, F.text.in_(["👨 Мужской", "👩 Женский", "Мужской", "Женский"]))
async def process_gender(message: Message, state: FSMContext):
    gender = "Мужской" if "Мужской" in message.text else "Женский"
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
        "📝 Напиши о себе\n"
        "(чем увлекаешься, что ищешь)\n\n"
        "⚠️ Без ссылок и юзернеймов!",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    # Проверка на запрещенные символы
    forbidden = ["@", "t.me/", "https://", "http://"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer("❌ Ссылки и юзернеймы запрещены!")
        return
    
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        "📸 Отправь свое фото\n"
        "(одно фото обязательно)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    # Сохраняем анкету
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
    conn.commit()
    
    await state.clear()
    await message.answer(
        "✅ АНКЕТА СОЗДАНА!\n\n"
        "Теперь можно смотреть анкеты 👀",
        reply_markup=get_main_keyboard()
    )

# ========== СМОТРЕТЬ АНКЕТЫ ==========
@dp.message(F.text == "👀 Смотреть")
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    # Проверяем наличие анкеты
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await message.answer("❌ Сначала создай анкету через /create")
        return
    
    # Проверяем лимиты
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    is_premium = user[0]
    views_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(
            f"❌ Лимит просмотров исчерпан ({limit})\n"
            f"Купи 💎 Премиум для увеличения лимита!"
        )
        return
    
    # Ищем анкету для просмотра
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
        await message.answer(
            "🍺 Ты посмотрел все анкеты!\n"
            "Заходи позже, появятся новые"
        )
        return
    
    # Сохраняем просмотр
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    conn.commit()
    
    # Формируем текст анкеты
    text = (
        f"👤 {profile[2]}, {profile[3]}\n"
        f"⚥ {profile[4]}\n"
        f"🏙 {profile[5]}\n\n"
        f"📝 {profile[6]}\n\n"
        f"❤️ {profile[10]} лайков"
    )
    
    # Кнопки
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data=f"like_{profile[1]}")
    builder.button(text="▶️ Дальше", callback_data="next_profile")
    builder.button(text="⚠️ Пожаловаться", callback_data=f"complaint_{profile[1]}")
    if profile[-1]:
        builder.button(text="📱 Написать", url=f"https://t.me/{profile[-1]}")
    builder.adjust(2, 1, 1)
    
    await message.answer_photo(
        photo=profile[7],
        caption=text,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "next_profile")
async def next_profile(callback: CallbackQuery):
    await callback.message.delete()
    await view_profiles(callback.message)

# ========== ЛАЙКИ ==========
@dp.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    from_user = callback.from_user.id
    to_user = int(callback.data.split("_")[1])
    
    if from_user == to_user:
        await callback.answer("❌ Нельзя лайкнуть себя!", show_alert=True)
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
            
            await callback.answer("💕 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Получаем имена
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (to_user,))
            to_username = cursor.fetchone()[0]
            
            # Уведомление первому
            builder1 = InlineKeyboardBuilder()
            if to_username:
                builder1.button(text=f"📱 Написать {to_name}", url=f"https://t.me/{to_username}")
            builder1.button(text="👀 Продолжить", callback_data="next_profile")
            builder1.adjust(1)
            
            await bot.send_message(
                from_user,
                f"💕 ВЗАИМНЫЙ ЛАЙК С {to_name}!\n\n"
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
                builder2.button(text=f"📱 Написать {from_name}", url=f"https://t.me/{from_username}")
            builder2.button(text="👀 Продолжить", callback_data="next_profile")
            builder2.adjust(1)
            
            await bot.send_message(
                to_user,
                f"💕 ВЗАИМНЫЙ ЛАЙК С {from_name}!\n\n"
                f"Теперь вы можете пообщаться!",
                reply_markup=builder2.as_markup()
            )
            
        else:
            await callback.answer("❤️ Лайк отправлен!")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== ЖАЛОБЫ ==========
@dp.callback_query(F.data.startswith("complaint_"))
async def complaint_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(complaint_user=user_id)
    
    builder = InlineKeyboardBuilder()
    reasons = ["Спам", "Оскорбления", "Фейк", "18+ контент", "Другое"]
    for reason in reasons:
        builder.button(text=reason, callback_data=f"complaint_reason_{reason}")
    builder.button(text="◀️ Отмена", callback_data="cancel")
    builder.adjust(2)
    
    await callback.message.edit_caption(
        caption="⚠️ Выбери причину жалобы:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ComplaintStates.reason)

@dp.callback_query(ComplaintStates.reason, F.data.startswith("complaint_reason_"))
async def process_complaint(callback: CallbackQuery, state: FSMContext):
    reason = callback.data.replace("complaint_reason_", "")
    data = await state.get_data()
    on_user = data.get("complaint_user")
    
    cursor.execute('''
        INSERT INTO complaints (from_user, on_user, reason, created_at)
        VALUES (?, ?, ?, ?)
    ''', (callback.from_user.id, on_user, reason, datetime.now().isoformat()))
    conn.commit()
    
    await state.clear()
    await callback.answer("✅ Жалоба отправлена администратору!", show_alert=True)
    await callback.message.delete()
    await cmd_start(callback.message)

# ========== СТАТИСТИКА ==========
@dp.message(F.text == "📊 Статистика")
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
        
        text = (
            f"📊 ТВОЯ СТАТИСТИКА\n\n"
            f"👁 ТЫ ПОСМОТРЕЛ: {viewed_count}\n"
            f"👁 ТЕБЯ ПОСМОТРЕЛИ: {my_views}\n"
            f"❤️ ТЫ ЛАЙКНУЛ: {likes_given}\n"
            f"❤️ ТЕБЯ ЛАЙКНУЛИ: {likes_received}\n"
            f"💕 ВЗАИМНЫХ ЛАЙКОВ: {mutual_count}\n\n"
            f"📈 ОСТАЛОСЬ ПРОСМОТРОВ: {limit - views_used}\n"
            f"📈 ОСТАЛОСЬ ЛАЙКОВ: {limit - likes_used}"
        )
        
        await message.answer(text)

# ========== ПРЕМИУМ ==========
@dp.message(F.text == "💎 Премиум")
async def show_premium(message: Message):
    text = (
        f"💎 ПРЕМИУМ ПИВЧИК\n\n"
        f"Бесплатный аккаунт:\n"
        f"• {FREE_LIMIT} просмотров\n"
        f"• {FREE_LIMIT} лайков\n\n"
        f"Премиум аккаунт:\n"
        f"• {PREMIUM_LIMIT} просмотров\n"
        f"• {PREMIUM_LIMIT} лайков\n"
        f"• Приоритетный показ\n"
        f"• Значок в профиле\n\n"
        f"💰 ЦЕНА:\n"
        f"• 50 ⭐ = 1 день\n"
        f"• 250 ⭐ = 7 дней\n"
        f"• 1000 ⭐ = 30 дней"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 Stars (1 день)", callback_data="buy_50")
    builder.button(text="⭐ 250 Stars (7 дней)", callback_data="buy_250")
    builder.button(text="⭐ 1000 Stars (30 дней)", callback_data="buy_1000")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def buy_premium(callback: CallbackQuery):
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
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])
    
    cursor.execute('''
        UPDATE users 
        SET is_premium = 1,
            premium_until = ?,
            likes_used = 0,
            views_used = 0
        WHERE user_id = ?
    ''', ((datetime.now() + timedelta(days=days)).isoformat(), user_id))
    conn.commit()
    
    await message.answer(
        f"✅ ПРЕМИУМ АКТИВИРОВАН НА {days} ДНЕЙ!\n\n"
        f"Теперь у тебя {PREMIUM_LIMIT} просмотров и лайков!"
    )

# ========== БАЛАНС ==========
@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    await message.answer(f"💰 ТВОЙ БАЛАНС: {balance} ⭐")

# ========== НАСТРОЙКИ ==========
@dp.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Уведомления", callback_data="notify")
    builder.button(text="🔐 Приватность", callback_data="privacy")
    builder.adjust(1)
    
    await message.answer("⚙️ НАСТРОЙКИ", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "notify")
async def notify_settings(callback: CallbackQuery):
    await callback.answer("🔔 Уведомления скоро будут доступны", show_alert=True)

@dp.callback_query(F.data == "privacy")
async def privacy_settings(callback: CallbackQuery):
    text = (
        "🔐 ПРИВАТНОСТЬ\n\n"
        "• Твои данные в безопасности\n"
        "• Фото видят только пользователи\n"
        "• Ты можешь удалить анкету в любой момент\n"
        "• Мы не передаем данные третьим лицам"
    )
    await callback.message.edit_text(text)

# ========== ПОМОЩЬ ==========
@dp.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    text = (
        "❓ ПОМОЩЬ\n\n"
        "📝 /create - создать анкету\n"
        "👤 Моя анкета - просмотр анкеты\n"
        "👀 Смотреть - смотреть анкеты\n"
        "❤️ Лайк - поставить лайк\n"
        "💕 Взаимный лайк - можно писать\n\n"
        "ПРАВИЛА:\n"
        "• Только реальные фото\n"
        "• Без оскорблений\n"
        "• Без спама\n"
        "• Возраст 18+\n\n"
        "По вопросам: @admin"
    )
    await message.answer(text)

# ========== РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ==========
@dp.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_create(callback.message, state)

@dp.callback_query(F.data == "edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.message.delete()
    await callback.message.answer(
        "📸 Отправь новое фото:",
        reply_markup=get_back_keyboard()
    )
    
    # Ждем фото
    @dp.message(F.photo)
    async def update_photo(message: Message):
        photo_id = message.photo[-1].file_id
        cursor.execute('UPDATE profiles SET photo = ? WHERE user_id = ?', (photo_id, user_id))
        conn.commit()
        await message.answer("✅ Фото обновлено!", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "delete_profile")
async def delete_profile_confirm(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="cancel")
    
    await callback.message.edit_caption(
        caption="⚠️ Ты уверен, что хочешь удалить анкету?\nЭто действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_delete")
async def delete_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cursor.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM likes WHERE from_user = ? OR to_user = ?', (user_id, user_id))
    cursor.execute('DELETE FROM views WHERE user_id = ? OR viewed_user_id = ?', (user_id, user_id))
    conn.commit()
    
    await callback.message.delete()
    await callback.message.answer(
        "✅ Анкета удалена!\n\n"
        "Чтобы создать новую, нажми /create",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

# ========== НАЗАД ==========
@dp.message(F.text == "◀️ Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM profiles')
    profiles = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "new"')
    complaints = cursor.fetchone()[0]
    
    text = (
        f"👑 АДМИН ПАНЕЛЬ\n\n"
        f"👥 Пользователей: {users}\n"
        f"📝 Анкет: {profiles}\n"
        f"💎 Премиум: {premium}\n"
        f"⚠️ Жалоб: {complaints}"
    )
    
    await message.answer(text)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🍺 ========== ПИВЧИК ==========")
    print("🍺 БОТ ЗАПУЩЕН!")
    print(f"🍺 АДМИН: {ADMIN_IDS[0]}")
    print("🍺 =============================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
