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
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]  # Твой ID
CRYPTO_BOT_TOKEN = "YOUR_CRYPTO_BOT_TOKEN"  # Токен CryptoBot (получишь у @CryptoBot)

PREMIUM_PRICE_STARS = 50  # Цена в звёздах Telegram
PREMIUM_PRICE_RUB = 100  # Цена в рублях для CryptoBot
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
        
        # Статистика
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                users_count INTEGER,
                profiles_count INTEGER,
                likes_count INTEGER,
                mutual_count INTEGER
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

# ========== КРАСИВОЕ ПРИВЕТСТВИЕ ==========
WELCOME_MESSAGE = """
╔══════════════════════════╗
║         🍺 ПИВЧИК        ║
╠══════════════════════════╣
║  Здесь люди находят      ║
║  друг друга за кружкой   ║
║  холодного пива!         ║
╠══════════════════════════╣
║ 🔥 Создай анкету         ║
║ 💕 Находи людей          ║
║ 💬 Общайся в ЛС          ║
╠══════════════════════════╣
║    👇 ЖМИ В МЕНЮ 👇      ║
╚══════════════════════════╝
"""

# ========== КНОПКИ НАЗАД ==========
BACK_BUTTONS = {
    "profile": "👤 К АНКЕТЕ",
    "main": "🍺 ГЛАВНОЕ МЕНЮ",
    "edit": "✏️ К РЕДАКТИРОВАНИЮ",
    "premium": "⭐ К ПРЕМИУМУ"
}

def get_back_keyboard(back_to: str = "main"):
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=BACK_BUTTONS.get(back_to, BACK_BUTTONS["main"])))
    return builder.as_markup(resize_keyboard=True)

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
    builder.adjust(2, 2, 2, 1)  # 3 ряда по 2 + 1
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
    builder.button(text="💰 БАЛАНС: " + str(balance) + " ⭐", callback_data="balance")
    builder.button(text="⚙️ НАСТРОЙКИ", callback_data="settings")
    builder.button(text="❓ ПОМОЩЬ", callback_data="help")
    
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def back_inline_button(back_to: str = "main"):
    """Инлайн кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 НАЗАД", callback_data=f"back_to_{back_to}")
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ КНОПОК НАЗАД ==========
@dp.message(F.text == "🍺 ГЛАВНОЕ МЕНЮ")
async def back_to_main_reply(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

@dp.message(F.text == "👤 К АНКЕТЕ")
async def back_to_profile_reply(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="my_profile"
    )
    await my_profile(callback)

@dp.message(F.text == "✏️ К РЕДАКТИРОВАНИЮ")
async def back_to_edit_reply(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="edit_profile_menu"
    )
    await edit_profile_menu_callback(callback)

@dp.message(F.text == "⭐ К ПРЕМИУМУ")
async def back_to_premium_reply(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="premium_info"
    )
    await premium_info(callback)

# ========== СТАРТ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    
    cursor = db.conn.cursor()
    
    # Регистрация
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
    
    # Красивое приветствие по центру
    await message.answer(
        f"<pre>{WELCOME_MESSAGE}</pre>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    # Дополнительно показываем инлайн меню
    await message.answer(
        "🍺 <b>Выбери действие:</b>",
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )

# ========== ПОПОЛНЕНИЕ БАЛАНСА ==========
@dp.message(F.text == "💰 ПОПОЛНИТЬ")
async def reply_balance(message: Message, state: FSMContext):
    await state.clear()
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        message=message,
        data="balance"
    )
    await show_balance(callback)

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor = db.conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    text = (
        "💰 <b>ТВОЙ БАЛАНС</b>\n\n"
        f"У тебя: <b>{balance} ⭐</b>\n\n"
        "<b>Способы пополнения:</b>\n"
        "1️⃣ Telegram Stars\n"
        "2️⃣ Криптовалюта (CryptoBot)\n\n"
        "<b>Цены:</b>\n"
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
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# ========== ПОКУПКА ЗА ЗВЁЗДЫ ==========
@dp.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars(callback: CallbackQuery):
    amount = int(callback.data.split("_")[2])
    
    # Конвертируем в дни
    days = amount // 50
    
    prices = [LabeledPrice(label="Премиум ПИВЧИК", amount=amount)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="🍺 Премиум ПИВЧИК",
        description=f"Премиум на {days} дней",
        payload=f"premium_{days}",
        provider_token="",  # Для Stars оставляем пустым
        currency="XTR",  # Валюта Stars
        prices=prices,
        start_parameter="time-machine-test"
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
    
    # Добавляем дни к премиуму
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
    
    # Записываем транзакцию
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
        f"🍺 <b>Оплата прошла успешно!</b>\n\n"
        f"Тебе добавлено {days} дней Премиума!\n"
        f"Баланс пополнен на {amount} ⭐",
        parse_mode="HTML"
    )

# ========== ПОКУПКА ЧЕРЕЗ КРИПТУ ==========
@dp.callback_query(F.data == "buy_crypto")
async def buy_crypto(callback: CallbackQuery):
    text = (
        "₿ <b>Покупка за криптовалюту</b>\n\n"
        "1️⃣ Перейди в бота <b>@CryptoBot</b>\n"
        "2️⃣ Создай счёт на сумму 100 RUB\n"
        "3️⃣ Отправь сюда ID платежа\n\n"
        "<b>Реквизиты:</b>\n"
        "Сумма: 100 RUB = 30 дней Премиума\n"
        "Валюта: USDT, BTC, TON"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_inline_button("main")
    )

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет прав админа")
        return
    
    cursor = db.conn.cursor()
    
    # Статистика
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
        "👑 <b>АДМИН ПАНЕЛЬ</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• 👥 Всего пользователей: {total_users}\n"
        f"• 📝 Всего анкет: {total_profiles}\n"
        f"• ⭐ Премиум: {premium_users}\n"
        f"• ❤️ Взаимных лайков: {mutual_likes}\n"
        f"• 💰 Донатов: {total_donations} ⭐\n\n"
        f"⚠️ <b>Жалоб:</b> {new_complaints}\n\n"
        f"<b>Команды:</b>\n"
        f"/broadcast - рассылка\n"
        f"/complaints - жалобы\n"
        f"/stats - детальная статистика\n"
        f"/give_premium - выдать премиум\n"
        f"/block - заблокировать"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 РАССЫЛКА", callback_data="admin_broadcast")
    builder.button(text="⚠️ ЖАЛОБЫ", callback_data="admin_complaints")
    builder.button(text="📊 СТАТИСТИКА", callback_data="admin_stats")
    builder.button(text="👥 ПОЛЬЗОВАТЕЛИ", callback_data="admin_users")
    builder.button(text="🍺 ЗАКРЫТЬ", callback_data="back_to_main")
    builder.adjust(2, 2, 1)
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав")
        return
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь сообщение для рассылки всем пользователям:",
        parse_mode="HTML",
        reply_markup=back_inline_button("main")
    )
    await state.set_state(ProfileStates.waiting_for_broadcast)

@dp.message(ProfileStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав")
        return
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_blocked = 0')
    users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    status_msg = await message.answer("📢 Начинаю рассылку...")
    
    for user in users:
        try:
            await bot.copy_message(
                chat_id=user[0],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent += 1
            await asyncio.sleep(0.05)  # Чтобы не забанили
        except:
            failed += 1
    
    await status_msg.edit_text(
        f"📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}",
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "admin_complaints")
async def admin_complaints(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав")
        return
    
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT c.*, u.username, u.first_name 
        FROM complaints c
        JOIN users u ON c.from_user = u.user_id
        WHERE c.status = "new"
        ORDER BY c.created_at DESC
        LIMIT 10
    ''')
    complaints = cursor.fetchall()
    
    if not complaints:
        await callback.message.edit_text(
            "✅ Новых жалоб нет",
            parse_mode="HTML",
            reply_markup=back_inline_button("main")
        )
        return
    
    text = "⚠️ <b>НОВЫЕ ЖАЛОБЫ:</b>\n\n"
    
    for c in complaints:
        text += f"🆔 {c[0]} | От: @{c[7]}\n"
        text += f"На: {c[2]} | Причина: {c[3]}\n"
        text += f"Дата: {c[4][:10]}\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ОТМЕТИТЬ РЕШЁННЫМИ", callback_data="admin_complaints_resolve")
    builder.button(text="🍺 НАЗАД", callback_data="back_to_main")
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав")
        return
    
    cursor = db.conn.cursor()
    
    # Статистика по дням
    cursor.execute('''
        SELECT date(joined_date), COUNT(*) 
        FROM users 
        WHERE joined_date > date('now', '-7 days')
        GROUP BY date(joined_date)
    ''')
    daily_users = cursor.fetchall()
    
    cursor.execute('''
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM transactions 
        WHERE status = "success"
        GROUP BY payment_method
    ''')
    payments = cursor.fetchall()
    
    text = "📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>\n\n"
    text += "<b>Новые пользователи по дням:</b>\n"
    
    for day in daily_users:
        text += f"• {day[0]}: +{day[1]}\n"
    
    text += "\n<b>Платежи:</b>\n"
    for p in payments:
        text += f"• {p[0]}: {p[1]} платежей на {p[2]} ⭐\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_inline_button("main")
    )

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.callback_query(F.data == "create_profile")
async def create_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "🍺 <b>Наливаем пивчика!</b>\n\n"
        "Давай создадим твою анкету\n\n"
        "Как тебя зовут?",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("main")
    )
    await state.set_state(ProfileStates.waiting_for_name)

@dp.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя. Максимум 50 символов.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        f"📅 <b>Сколько тебе лет?</b> (от {MIN_AGE} до {MAX_AGE})",
        parse_mode="HTML"
    )
    await state.set_state(ProfileStates.waiting_for_age)

# ... (продолжение следует - остальные обработчики создания анкеты такие же как в прошлой версии)
# Я не буду копировать их все сюда для краткости, но они остаются без изменений

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
            f"❌ <b>Лимит просмотров исчерпан</b> ({limit})\n"
            "Купи <b>ПРЕМИУМ</b> для увеличения лимита!",
            parse_mode="HTML",
            reply_markup=back_inline_button("main")
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
            "🍺 <b>Ты посмотрел все анкеты!</b>\n"
            "Заходи позже, появятся новые",
            parse_mode="HTML",
            reply_markup=back_inline_button("main")
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
        f"🍺 <b>{profile[2]}, {profile[3]}</b>\n"
        f"⚥ Пол: {profile[4]}\n"
        f"🏙 Город: {profile[5]}\n"
        f"🎯 Интересы: {interests_text}\n\n"
        f"📝 {profile[6]}\n\n"
        f"❤️ Лайков: {profile[11]} | 👁 Просмотров: {profile[10]}"
    )
    
    # Кнопки для просмотра
    builder = InlineKeyboardBuilder()
    builder.button(text="🍺 ЛАЙКНУТЬ", callback_data=f"like_{profile[1]}")
    builder.button(text="⏭ ДАЛЬШЕ", callback_data="view_profiles")
    
    if profile[-1]:  # если есть username
        builder.button(text=f"📱 НАПИСАТЬ @{profile[-1]}", url=f"https://t.me/{profile[-1]}")
    
    builder.button(text="⚠️ ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    
    if photos:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photos[0],
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
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
            cursor.execute('''
                INSERT OR IGNORE INTO mutual_likes (user1, user2, created_at)
                VALUES (?, ?, ?)
            ''', (min(from_user, to_user), max(from_user, to_user), datetime.now().isoformat()))
            
            cursor.execute('''
                UPDATE likes SET is_mutual = 1 
                WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ''', (from_user, to_user, to_user, from_user))
            
            db.conn.commit()
            
            # Получаем информацию
            cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (to_user,))
            to_user_data = cursor.fetchone()
            to_username = to_user_data[0]
            to_name = to_user_data[1]
            
            cursor.execute('SELECT name FROM profiles WHERE user_id = ?', (to_user,))
            profile_name = cursor.fetchone()
            to_profile_name = profile_name[0] if profile_name else to_name
            
            await callback.answer("🍺 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
            
            # Кнопка для перехода в ЛС
            builder = InlineKeyboardBuilder()
            if to_username:
                builder.button(text=f"📱 НАПИСАТЬ {to_profile_name}", url=f"https://t.me/{to_username}")
            builder.button(text="🍺 ПРОДОЛЖИТЬ", callback_data="view_profiles")
            builder.button(text="🍺 В МЕНЮ", callback_data="back_to_main")
            builder.adjust(1, 2)
            
            await bot.send_message(
                from_user,
                f"🍺 <b>Взаимный лайк с {to_profile_name}!</b>\n\n"
                f"Теперь вы можете пообщаться!",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
            # И для второго
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
                f"🍺 <b>Взаимный лайк с {from_profile_name}!</b>\n\n"
                f"Теперь вы можете пообщаться!",
                parse_mode="HTML",
                reply_markup=builder2.as_markup()
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
            f"⭐ <b>У ТЕБЯ ПРЕМИУМ!</b>\n\n"
            f"📅 Действует до: {until}\n\n"
            f"<b>Твои бонусы:</b>\n"
            f"• 🍺 {PREMIUM_LIMIT} просмотров\n"
            f"• 🍺 {PREMIUM_LIMIT} лайков\n"
            f"• ⭐ Значок в анкете\n"
            f"• 🔥 Показ в топе"
        )
    else:
        text = (
            f"⭐ <b>ПРЕМИУМ ПИВЧИК</b>\n\n"
            f"<b>Лимиты:</b>\n"
            f"• Бесплатно: {FREE_LIMIT} просмотров/лайков\n"
            f"• Премиум: {PREMIUM_LIMIT} просмотров/лайков\n\n"
            f"<b>Бонусы:</b>\n"
            f"• 🍺 Больше анкет\n"
            f"• ⭐ Значок в профиле\n"
            f"• 🔥 Показ в топе\n\n"
            f"💰 <b>Цена:</b>\n"
            f"• 50 ⭐ = 1 день\n"
            f"• 250 ⭐ = 7 дней\n"
            f"• 1000 ⭐ = 30 дней\n\n"
            f"Хочешь больше возможностей?"
        )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 50 STARS (1 день)", callback_data="buy_stars_50")
    builder.button(text="⭐ 250 STARS (7 дней)", callback_data="buy_stars_250")
    builder.button(text="⭐ 1000 STARS (30 дней)", callback_data="buy_stars_1000")
    builder.button(text="₿ КРИПТА", callback_data="buy_crypto")
    builder.button(text="🍺 НАЗАД", callback_data="back_to_main")
    builder.adjust(2, 1, 1, 1)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# ========== ОБРАБОТЧИКИ НАЗАД ==========
@dp.callback_query(F.data.startswith("back_to_"))
async def back_to_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    back_to = callback.data.replace("back_to_", "")
    
    if back_to == "main":
        await callback.message.delete()
        await cmd_start(callback.message, None)
    elif back_to == "profile":
        await my_profile(callback)
    elif back_to == "edit":
        await edit_profile_menu_callback(callback)
    elif back_to == "premium":
        await premium_info(callback)

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
    print("🍺 Оплата: Stars + Крипта")
    print("🍺 =================================")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
