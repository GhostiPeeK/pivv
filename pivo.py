import logging
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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

# Таблицы
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

cursor.execute('''
    CREATE TABLE IF NOT EXISTS views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        viewed_user_id INTEGER,
        viewed_at TEXT,
        UNIQUE(user_id, viewed_user_id)
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

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="👤 МОЯ АНКЕТА"), KeyboardButton(text="👀 СМОТРЕТЬ")],
        [KeyboardButton(text="💎 ПРЕМИУМ"), KeyboardButton(text="📊 СТАТИСТИКА")],
        [KeyboardButton(text="⚙️ НАСТРОЙКИ"), KeyboardButton(text="❓ ПОМОЩЬ")],
        [KeyboardButton(text="💰 БАЛАНС")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    kb = [[KeyboardButton(text="◀️ НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    kb = [
        [KeyboardButton(text="👨 МУЖСКОЙ"), KeyboardButton(text="👩 ЖЕНСКИЙ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, balance)
        VALUES (?, ?, ?, ?, 0)
    ''', (user_id, message.from_user.username, message.from_user.first_name, datetime.now().isoformat()))
    conn.commit()
    
    await message.answer(
        f"🍺 ДОБРО ПОЖАЛОВАТЬ В ПИВЧИК!\n\n"
        f"🔞 Здесь люди находят друг друга\n\n"
        f"👇 Выбирай в меню:",
        reply_markup=get_main_keyboard()
    )
    
    await show_main_menu(message)

async def show_main_menu(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    has_profile = cursor.fetchone() is not None
    
    cursor.execute('SELECT is_premium, views_used, likes_used, balance FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    is_premium = user[0] if user else False
    views_used = user[1] if user else 0
    likes_used = user[2] if user else 0
    balance = user[3] if user else 0
    
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    builder = InlineKeyboardBuilder()
    
    if has_profile:
        builder.button(text=f"👤 МОЯ АНКЕТА", callback_data="my_profile")
        builder.button(text=f"👀 СМОТРЕТЬ ({limit - views_used})", callback_data="view_profiles")
    else:
        builder.button(text=f"📝 СОЗДАТЬ АНКЕТУ", callback_data="create_profile")
    
    builder.button(text=f"💎 ПРЕМИУМ", callback_data="premium_info")
    builder.button(text=f"💰 БАЛАНС: {balance} ⭐", callback_data="balance")
    builder.button(text=f"◀️ НАЗАД", callback_data="back")
    
    builder.adjust(1, 2, 1, 1)
    
    await message.answer("🍺 МЕНЮ:", reply_markup=builder.as_markup())

# ========== ОБРАБОТКА REPLY КНОПОК (ИСПРАВЛЕНО) ==========
@dp.message(F.text == "👤 МОЯ АНКЕТА")
async def my_profile_reply(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer("❌ У тебя ещё нет анкеты!\nНажни 📝 СОЗДАТЬ АНКЕТУ в меню")
        return
    
    text = (
        f"👤 ТВОЯ АНКЕТА\n\n"
        f"Имя: {profile[2]}\n"
        f"Возраст: {profile[3]}\n"
        f"Пол: {profile[4]}\n"
        f"Город: {profile[5]}\n"
        f"О себе: {profile[6]}\n\n"
        f"Просмотров: {profile[9]}\n"
        f"Лайков: {profile[10]}"
    )
    
    if profile[7]:
        await message.answer_photo(photo=profile[7], caption=text)
    else:
        await message.answer(text)

@dp.message(F.text == "👀 СМОТРЕТЬ")
async def view_profiles_reply(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await message.answer("❌ Сначала создай анкету!")
        return
    
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    is_premium = user[0]
    views_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(f"❌ Лимит просмотров исчерпан ({limit})\nКупи 💎 ПРЕМИУМ")
        return
    
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
        await message.answer("🍺 Ты посмотрел все анкеты!\nЗаходи позже")
        return
    
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    conn.commit()
    
    text = (
        f"👤 {profile[2]}, {profile[3]}\n"
        f"🏙 {profile[5]}\n\n"
        f"{profile[6]}\n\n"
        f"❤️ {profile[10]} | 👁 {profile[9]}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ ЛАЙК", callback_data=f"like_{profile[1]}")
    builder.button(text="▶️ ДАЛЬШЕ", callback_data="next_profile")
    if profile[-1]:
        builder.button(text="📱 НАПИСАТЬ", url=f"https://t.me/{profile[-1]}")
    builder.button(text="◀️ МЕНЮ", callback_data="back")
    builder.adjust(2, 1, 1)
    
    await message.answer_photo(
        photo=profile[7],
        caption=text,
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == "💎 ПРЕМИУМ")
async def premium_reply(message: Message):
    text = (
        f"💎 ПРЕМИУМ ПИВЧИК\n\n"
        f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
        f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
        f"💰 ЦЕНА:\n"
        f"• 50 ⭐ = 1 день\n"
        f"• 250 ⭐ = 7 дней\n"
        f"• 1000 ⭐ = 30 дней\n\n"
        f"После покупки лимиты обновятся!"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 STARS (1 день)", callback_data="buy_50")
    builder.button(text="⭐ 250 STARS (7 дней)", callback_data="buy_250")
    builder.button(text="⭐ 1000 STARS (30 дней)", callback_data="buy_1000")
    builder.button(text="◀️ НАЗАД", callback_data="back")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text == "📊 СТАТИСТИКА")
async def stats_reply(message: Message):
    user_id = message.from_user.id
    
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
            (SELECT COUNT(*) FROM likes WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)) as mutual_count
        FROM users u
        LEFT JOIN profiles p ON u.user_id = p.user_id
        WHERE u.user_id = ?
    ''', (user_id, user_id, user_id, user_id, user_id, user_id))
    
    stats = cursor.fetchone()
    
    if stats:
        text = (
            f"📊 ТВОЯ СТАТИСТИКА\n\n"
            f"👁 ТЕБЯ ПОСМОТРЕЛИ: {stats[3]}\n"
            f"👁 ТЫ ПОСМОТРЕЛ: {stats[5]}\n"
            f"❤️ ТЕБЯ ЛАЙКНУЛИ: {stats[4]}\n"
            f"❤️ ТЫ ЛАЙКНУЛ: {stats[6]}\n"
            f"💕 ВЗАИМНЫХ ЛАЙКОВ: {stats[8]}\n\n"
            f"📈 ОСТАЛОСЬ ПРОСМОТРОВ: {PREMIUM_LIMIT if stats[0] else FREE_LIMIT - stats[1]}\n"
            f"📈 ОСТАЛОСЬ ЛАЙКОВ: {PREMIUM_LIMIT if stats[0] else FREE_LIMIT - stats[2]}"
        )
        await message.answer(text)

@dp.message(F.text == "⚙️ НАСТРОЙКИ")
async def settings_reply(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 УВЕДОМЛЕНИЯ", callback_data="notify")
    builder.button(text="🔐 ПРИВАТНОСТЬ", callback_data="privacy")
    builder.button(text="◀️ НАЗАД", callback_data="back")
    builder.adjust(1)
    
    await message.answer("⚙️ НАСТРОЙКИ", reply_markup=builder.as_markup())

@dp.message(F.text == "❓ ПОМОЩЬ")
async def help_reply(message: Message):
    text = (
        "❓ ПОМОЩЬ\n\n"
        "📝 СОЗДАТЬ АНКЕТУ - заполни анкету\n"
        "👀 СМОТРЕТЬ - смотри анкеты\n"
        "❤️ ЛАЙК - ставь лайки\n"
        "💕 ВЗАИМНЫЙ ЛАЙК - можно писать\n\n"
        "ПРАВИЛА:\n"
        "• Только реальные фото\n"
        "• Без оскорблений\n"
        "• Возраст 18+\n\n"
        "ПО ВОПРОСАМ: @admin"
    )
    await message.answer(text)

@dp.message(F.text == "💰 БАЛАНС")
async def balance_reply(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ ПОПОЛНИТЬ", callback_data="balance")
    builder.button(text="◀️ НАЗАД", callback_data="back")
    
    await message.answer(f"💰 ТВОЙ БАЛАНС: {balance} ⭐", reply_markup=builder.as_markup())

@dp.message(F.text == "◀️ НАЗАД")
async def back_reply(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "📝 СОЗДАНИЕ АНКЕТЫ\n\n"
        "Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
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

@dp.message(ProfileStates.gender, F.text.in_(["👨 МУЖСКОЙ", "👩 ЖЕНСКОЙ", "МУЖСКОЙ", "ЖЕНСКОЙ"]))
async def process_gender(message: Message, state: FSMContext):
    gender = "Мужской" if "МУЖСКОЙ" in message.text else "Женский"
    await state.update_data(gender=gender)
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "📝 Напиши о себе\n(чем увлекаешься, что ищешь)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer(
        "📸 Отправь свое фото\n(одно фото обязательно)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
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
        "✅ АНКЕТА СОЗДАНА!\n\nТеперь можно смотреть анкеты 👀",
        reply_markup=get_main_keyboard()
    )
    await show_main_menu(message)

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
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (to_user,))
            to_username = cursor.fetchone()[0]
            
            builder1 = InlineKeyboardBuilder()
            if to_username:
                builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
            builder1.button(text="▶️ ПРОДОЛЖИТЬ", callback_data="view_profiles")
            builder1.adjust(1)
            
            await bot.send_message(
                from_user,
                f"💕 ВЗАИМНЫЙ ЛАЙК С {to_name}!\n\nТеперь вы можете пообщаться!",
                reply_markup=builder1.as_markup()
            )
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (from_user,))
            from_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (from_user,))
            from_username = cursor.fetchone()[0]
            
            builder2 = InlineKeyboardBuilder()
            if from_username:
                builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
            builder2.button(text="▶️ ПРОДОЛЖИТЬ", callback_data="view_profiles")
            builder2.adjust(1)
            
            await bot.send_message(
                to_user,
                f"💕 ВЗАИМНЫЙ ЛАЙК С {from_name}!\n\nТеперь вы можете пообщаться!",
                reply_markup=builder2.as_markup()
            )
            
        else:
            await callback.answer("❤️ ЛАЙК ОТПРАВЛЕН!")
            
    except sqlite3.IntegrityError:
        await callback.answer("❌ Ты уже лайкал эту анкету", show_alert=True)

# ========== НАВИГАЦИЯ ==========
@dp.callback_query(F.data == "next_profile")
async def next_profile(callback: CallbackQuery):
    await callback.message.delete()
    await view_profiles_reply(callback.message)

@dp.callback_query(F.data == "back")
async def back_callback(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

@dp.callback_query(F.data == "my_profile")
async def my_profile_callback(callback: CallbackQuery):
    await callback.message.delete()
    await my_profile_reply(callback.message)

@dp.callback_query(F.data == "view_profiles")
async def view_profiles_callback(callback: CallbackQuery):
    await callback.message.delete()
    await view_profiles_reply(callback.message)

@dp.callback_query(F.data == "premium_info")
async def premium_info_callback(callback: CallbackQuery):
    await callback.message.delete()
    await premium_reply(callback.message)

@dp.callback_query(F.data == "balance")
async def balance_callback(callback: CallbackQuery):
    await callback.message.delete()
    await balance_reply(callback.message)

@dp.callback_query(F.data == "notify")
async def notify_callback(callback: CallbackQuery):
    await callback.answer("🔔 Скоро будут уведомления", show_alert=True)

@dp.callback_query(F.data == "privacy")
async def privacy_callback(callback: CallbackQuery):
    text = (
        "🔐 ПРИВАТНОСТЬ\n\n"
        "• Твои данные в безопасности\n"
        "• Фото видят только пользователи\n"
        "• Можно удалить анкету (напиши админу)\n"
        "• Мы не передаем данные третьим лицам"
    )
    await callback.message.edit_text(text)

# ========== ПРЕМИУМ ==========
@dp.callback_query(F.data.startswith("buy_"))
async def buy_premium(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум ПИВЧИК", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💎 ПРЕМИУМ ПИВЧИК",
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

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ НЕТ ДОСТУПА")
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM profiles')
    profiles = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1')
    mutual = cursor.fetchone()[0]
    
    await message.answer(
        f"👑 АДМИН ПАНЕЛЬ\n\n"
        f"👥 ПОЛЬЗОВАТЕЛЕЙ: {users}\n"
        f"📝 АНКЕТ: {profiles}\n"
        f"💎 ПРЕМИУМ: {premium}\n"
        f"💕 ВЗАИМНЫХ: {mutual}"
    )

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🍺 ========== ПИВЧИК ==========")
    print("🍺 БОТ ЗАПУЩЕН!")
    print(f"🍺 АДМИН: {ADMIN_IDS[0]}")
    print("🍺 ВЕРСИЯ: РАБОЧАЯ")
    print("🍺 =============================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
