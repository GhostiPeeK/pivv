import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery  # ВОТ ЭТОТ ИМПОРТ БЫЛ ПРОПУЩЕН!
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
    "crown": "👑"
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

# ========== КЛАВИАТУРЫ В СТИЛЕ ПИВЧИК ==========
def get_main_keyboard():
    """Главная клавиатура"""
    kb = [
        [KeyboardButton(text=f"{STYLE['profile']} МОЯ АНКЕТА"), KeyboardButton(text=f"{STYLE['view']} СМОТРЕТЬ")],
        [KeyboardButton(text=f"{STYLE['premium']} ПРЕМИУМ"), KeyboardButton(text=f"{STYLE['stats']} СТАТИСТИКА")],
        [KeyboardButton(text=f"{STYLE['settings']} НАСТРОЙКИ"), KeyboardButton(text=f"{STYLE['help']} ПОМОЩЬ")],
        [KeyboardButton(text=f"{STYLE['balance']} БАЛАНС")]
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
    
    # Приветствие в стиле ПИВЧИК
    welcome_text = f"""
{STYLE['header']}

🍺 {message.from_user.first_name}, добро пожаловать в ПИВЧИК!
🔞 Здесь люди находят друг друга

🚀 ЧТО ТЕБЯ ЖДЕТ:
{STYLE['profile']} Создай анкету
{STYLE['view']} Смотри анкеты
{STYLE['like']} Ставь лайки
{STYLE['mutual']} Общайся с теми, кто лайкнул в ответ
{STYLE['premium']} Премиум - больше возможностей

👇 ЖМИ КНОПКИ ВНИЗУ И ПОГНАЛИ!
{STYLE['divider']}
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== МОЯ АНКЕТА ==========
@dp.message(F.text == f"{STYLE['profile']} МОЯ АНКЕТА")
async def my_profile(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    if not profile:
        await message.answer(
            f"{STYLE['error']} У тебя ещё нет анкеты!\n"
            f"Нажми /create чтобы создать анкету"
        )
        return
    
    cursor.execute('SELECT COUNT(*) FROM views WHERE viewed_user_id = ?', (user_id,))
    views = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM likes WHERE to_user = ?', (user_id,))
    likes = cursor.fetchone()[0]
    
    cursor.execute('SELECT is_premium FROM users WHERE user_id = ?', (user_id,))
    is_premium = cursor.fetchone()[0]
    premium_badge = f" {STYLE['premium']}" if is_premium else ""
    
    text = f"""
{STYLE['divider']}
{STYLE['profile']} ТВОЯ АНКЕТА{premium_badge}
{STYLE['divider']}

👤 Имя: {profile[2]}
📅 Возраст: {profile[3]}
⚥ Пол: {profile[4]}
🏙 Город: {profile[5]}

📝 О себе:
{profile[6]}

{STYLE['divider']}
📊 СТАТИСТИКА:
👁 Просмотров: {views}
❤️ Лайков: {likes}
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{STYLE['beer']} РЕДАКТИРОВАТЬ", callback_data="edit_profile")
    builder.button(text=f"📸 ФОТО", callback_data="edit_photo")
    builder.button(text=f"{STYLE['error']} УДАЛИТЬ", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if profile[7]:
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
        f"{STYLE['divider']}\n"
        f"🍺 СОЗДАНИЕ АНКЕТЫ\n"
        f"{STYLE['divider']}\n\n"
        f"Как тебя зовут?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer(f"{STYLE['error']} Слишком длинное имя. Максимум 50 символов.")
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
        await message.answer(f"{STYLE['error']} Введи число от {MIN_AGE} до {MAX_AGE}")
        return
    
    await state.update_data(age=age)
    await message.answer(
        "👤 Выбери пол:",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(ProfileStates.gender)

@dp.message(ProfileStates.gender, F.text.in_(["🍺 МУЖСКОЙ", "🍺 ЖЕНСКИЙ", "МУЖСКОЙ", "ЖЕНСКИЙ"]))
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
    if len(message.text) > 50:
        await message.answer(f"{STYLE['error']} Слишком длинное название города")
        return
    
    await state.update_data(city=message.text)
    await message.answer(
        f"📝 Напиши о себе\n"
        f"(чем увлекаешься, что ищешь)\n\n"
        f"{STYLE['warning']} Без ссылок и юзернеймов!",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(f"{STYLE['error']} Ссылки и юзернеймы запрещены!")
        return
    
    if len(message.text) > 500:
        await message.answer(f"{STYLE['error']} Слишком длинное описание. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь свое фото\n"
        f"(одно фото обязательно)",
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
        f"{STYLE['divider']}\n"
        f"{STYLE['success']} АНКЕТА СОЗДАНА!\n"
        f"{STYLE['divider']}\n\n"
        f"Теперь можно смотреть анкеты {STYLE['view']}",
        reply_markup=get_main_keyboard()
    )

# ========== СМОТРЕТЬ АНКЕТЫ ==========
@dp.message(F.text == f"{STYLE['view']} СМОТРЕТЬ")
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    cursor.execute('SELECT profile_id FROM profiles WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        await message.answer(f"{STYLE['error']} Сначала создай анкету через /create")
        return
    
    cursor.execute('SELECT is_premium, views_used FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    is_premium = user[0]
    views_used = user[1]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(
            f"{STYLE['error']} Лимит просмотров исчерпан ({limit})\n"
            f"Купи {STYLE['premium']} ПРЕМИУМ для увеличения лимита!"
        )
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
        await message.answer(
            f"{STYLE['beer']} Ты посмотрел все анкеты!\n"
            f"Заходи позже, появятся новые"
        )
        return
    
    cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    cursor.execute('UPDATE users SET views_used = views_used + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    conn.commit()
    
    text = f"""
{STYLE['divider']}
🍺 {profile[2]}, {profile[3]}
⚥ {profile[4]}
🏙 {profile[5]}

📝 {profile[6]}

❤️ {profile[10]} лайков
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{STYLE['like']} ЛАЙК", callback_data=f"like_{profile[1]}")
    builder.button(text=f"{STYLE['next']} ДАЛЬШЕ", callback_data="next_profile")
    builder.button(text=f"{STYLE['warning']} ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    if profile[-1]:
        builder.button(text=f"📱 НАПИСАТЬ", url=f"https://t.me/{profile[-1]}")
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
        await callback.answer(f"{STYLE['error']} Нельзя лайкнуть себя!", show_alert=True)
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
            
            await callback.answer(f"{STYLE['mutual']} ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            to_name = cursor.fetchone()[0]
            
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (to_user,))
            to_username = cursor.fetchone()[0]
            
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

# ========== ПРЕМИУМ ==========
@dp.message(F.text == f"{STYLE['premium']} ПРЕМИУМ")
async def show_premium(message: Message):
    text = f"""
{STYLE['divider']}
{STYLE['premium']} ПРЕМИУМ ПИВЧИК
{STYLE['divider']}

📊 ЛИМИТЫ:
• Бесплатно: {FREE_LIMIT} 👁/❤️
• Премиум: {PREMIUM_LIMIT} 👁/❤️

✨ БОНУСЫ ПРЕМИУМ:
• Приоритетный показ анкеты
• Специальный значок {STYLE['premium']}
• Ранний доступ к новым функциям

💰 ЦЕНА:
• 50 ⭐ = 1 день
• 250 ⭐ = 7 дней
• 1000 ⭐ = 30 дней
{STYLE['divider']}
"""
    
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
        f"{STYLE['divider']}\n"
        f"{STYLE['success']} ПРЕМИУМ АКТИВИРОВАН!\n"
        f"{STYLE['divider']}\n\n"
        f"На {days} дней\n"
        f"Теперь у тебя {PREMIUM_LIMIT} 👁 и ❤️"
    )

# ========== СТАТИСТИКА ==========
@dp.message(F.text == f"{STYLE['stats']} СТАТИСТИКА")
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
        
        text = f"""
{STYLE['divider']}
{STYLE['stats']} ТВОЯ СТАТИСТИКА
{STYLE['divider']}

👁 ТЫ ПОСМОТРЕЛ: {viewed_count}
👁 ТЕБЯ ПОСМОТРЕЛИ: {my_views}
❤️ ТЫ ЛАЙКНУЛ: {likes_given}
❤️ ТЕБЯ ЛАЙКНУЛИ: {likes_received}
{STYLE['mutual']} ВЗАИМНЫХ: {mutual_count}

📈 ОСТАЛОСЬ:
• 👁 {limit - views_used}
• ❤️ {limit - likes_used}
{STYLE['divider']}
"""
        
        await message.answer(text)

# ========== НАСТРОЙКИ ==========
@dp.message(F.text == f"{STYLE['settings']} НАСТРОЙКИ")
async def show_settings(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 УВЕДОМЛЕНИЯ", callback_data="notify")
    builder.button(text="🔐 ПРИВАТНОСТЬ", callback_data="privacy")
    builder.button(text=f"{STYLE['back']} НАЗАД", callback_data="back")
    builder.adjust(1)
    
    await message.answer(f"{STYLE['settings']} НАСТРОЙКИ", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "notify")
async def notify_settings(callback: CallbackQuery):
    await callback.answer("🔔 Уведомления скоро будут", show_alert=True)

@dp.callback_query(F.data == "privacy")
async def privacy_settings(callback: CallbackQuery):
    text = f"""
{STYLE['divider']}
🔐 ПРИВАТНОСТЬ
{STYLE['divider']}

• Твои данные в безопасности
• Фото видят только пользователи
• Можно удалить анкету в любой момент
• Мы не передаем данные третьим лицам
{STYLE['divider']}
"""
    await callback.message.edit_text(text)

# ========== ПОМОЩЬ ==========
@dp.message(F.text == f"{STYLE['help']} ПОМОЩЬ")
async def show_help(message: Message):
    text = f"""
{STYLE['divider']}
{STYLE['help']} ПОМОЩЬ
{STYLE['divider']}

🍺 КАК ПОЛЬЗОВАТЬСЯ:

{STYLE['beer']} /create - создать анкету
{STYLE['profile']} МОЯ АНКЕТА - просмотр
{STYLE['view']} СМОТРЕТЬ - листать анкеты
{STYLE['like']} ЛАЙК - поставить лайк
{STYLE['mutual']} ВЗАИМНЫЙ ЛАЙК - можно писать

📊 КОМАНДЫ:
/premium - купить премиум
/stats - статистика
/help - помощь

⚠️ ПРАВИЛА:
• Только реальные фото
• Без оскорблений
• Без спама
• Возраст 18+

👨‍💻 По вопросам: @admin
{STYLE['divider']}
"""
    await message.answer(text)

# ========== БАЛАНС ==========
@dp.message(F.text == f"{STYLE['balance']} БАЛАНС")
async def show_balance(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    await message.answer(f"{STYLE['balance']} ТВОЙ БАЛАНС: {balance} ⭐")

# ========== НАЗАД ==========
@dp.message(F.text == f"{STYLE['back']} НАЗАД")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

@dp.callback_query(F.data == "back")
async def back_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message)

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(f"{STYLE['error']} Нет доступа")
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM profiles')
    profiles = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "new"')
    complaints = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1')
    mutual = cursor.fetchone()[0]
    
    text = f"""
{STYLE['divider']}
{STYLE['crown']} АДМИН ПАНЕЛЬ
{STYLE['divider']}

👥 ПОЛЬЗОВАТЕЛЕЙ: {users}
📝 АНКЕТ: {profiles}
💎 ПРЕМИУМ: {premium}
💕 ВЗАИМНЫХ: {mutual}
⚠️ ЖАЛОБ: {complaints}
{STYLE['divider']}
"""
    
    await message.answer(text)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
{STYLE['header']}
{STYLE['beer']} БОТ ЗАПУЩЕН!
{STYLE['beer']} АДМИН: {ADMIN_IDS[0]}
{STYLE['beer']} СТИЛЬ: ПИВЧИК
{STYLE['beer']} СТАТУС: РАБОТАЕТ НА 100%
{STYLE['header']}
""")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
