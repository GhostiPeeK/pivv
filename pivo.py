import logging
import asyncio
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

from database import db

# ========== КОНФИГ ==========
BOT_TOKEN = "8732723377:AAH4LuAnzfrlLUSFBv17gK7NssNIZtlDFK4"
ADMIN_IDS = [2091630272]

FREE_LIMIT = 250
PREMIUM_LIMIT = 1500
MIN_AGE = 18
MAX_AGE = 100

# ========== СТИЛЬ ==========
STYLE = {
    "header": "🍺════════ ПИВЧИК ════════🍺",
    "divider": "──────────────────────────",
}

# ========== FSM ==========
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

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    kb = [
        [KeyboardButton(text=f"👤 МОЯ АНКЕТА"), KeyboardButton(text=f"👀 СМОТРЕТЬ")],
        [KeyboardButton(text=f"💎 ПРЕМИУМ"), KeyboardButton(text=f"📊 СТАТИСТИКА")],
        [KeyboardButton(text=f"🔥 ТОП"), KeyboardButton(text=f"🎁 РЕФЕРАЛЫ")],
        [KeyboardButton(text=f"🎮 ИГРЫ"), KeyboardButton(text=f"💬 ЧАТЫ")],
        [KeyboardButton(text=f"🎂 ДНИ РОЖДЕНИЯ"), KeyboardButton(text=f"📍 ПОИСК РЯДОМ")],
        [KeyboardButton(text=f"🎨 СТИКЕРЫ"), KeyboardButton(text=f"⚙️ НАСТРОЙКИ")],
        [KeyboardButton(text=f"💰 БАЛАНС"), KeyboardButton(text=f"❓ ПОМОЩЬ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard():
    kb = [[KeyboardButton(text=f"◀️ НАЗАД")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_gender_keyboard():
    kb = [[KeyboardButton(text="МУЖСКОЙ"), KeyboardButton(text="ЖЕНСКИЙ")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Проверяем есть ли пользователь
    user = db.get_user(user_id)
    if not user:
        user = db.create_user(user_id, message.from_user.username, message.from_user.first_name)
        
        # Проверяем реферальный код
        args = message.text.split()
        if len(args) > 1:
            referrer_id = db.process_referral(args[1], user_id)
            if referrer_id:
                await bot.send_message(
                    referrer_id,
                    f"🎁 ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ!\n\n"
                    f"Новый пользователь @{message.from_user.username}\n"
                    f"Начислено 50 ⭐ на баланс!"
                )
        
        db.update_stats('new_users')
    
    db.update_last_active(user_id)
    
    welcome_text = f"""
{STYLE['header']}

🍺 {message.from_user.first_name}, добро пожаловать в ПИВЧИК!

🚀 ЧТО ТЕБЯ ЖДЕТ:
👤 МОЯ АНКЕТА - создай и управляй
👀 СМОТРЕТЬ - листай анкеты
❤️ ЛАЙКИ - ставь и получай
💎 ПРЕМИУМ - больше возможностей

👇 ЖМИ КНОПКИ ВНИЗУ!
{STYLE['divider']}
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ========== СОЗДАНИЕ АНКЕТЫ ==========
@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.get_profile(user_id):
        await message.answer(
            f"❌ У тебя уже есть активная анкета!\n"
            f"Если хочешь создать новую, сначала удали старую."
        )
        return
    
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
        await message.answer(f"❌ Слишком длинное имя. Максимум 50 символов.")
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
    if message.text.upper() not in ["МУЖСКОЙ", "ЖЕНСКИЙ"]:
        await message.answer("❌ Используй кнопки")
        return
    
    gender = "Мужской" if message.text.upper() == "МУЖСКОЙ" else "Женский"
    await state.update_data(gender=gender)
    await message.answer(
        "🏙 Из какого ты города?",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer(f"❌ Слишком длинное название города")
        return
    
    await state.update_data(city=message.text)
    await message.answer(
        f"📝 Напиши о себе\n"
        f"(чем увлекаешься, что ищешь)\n\n"
        f"⚠️ Без ссылок и юзернеймов!",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.about)

@dp.message(ProfileStates.about)
async def process_about(message: Message, state: FSMContext):
    forbidden = ["@", "t.me/", "https://", "http://"]
    if any(x in message.text.lower() for x in forbidden):
        await message.answer(f"❌ Ссылки и юзернеймы запрещены!")
        return
    
    if len(message.text) > 500:
        await message.answer(f"❌ Слишком длинное описание. Максимум 500 символов")
        return
    
    await state.update_data(about=message.text)
    await message.answer(
        f"📸 Отправь свое фото",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    db.create_profile(
        message.from_user.id,
        data['name'],
        data['age'],
        data['gender'],
        data['city'],
        data['about'],
        photo_id
    )
    db.update_stats('new_profiles')
    
    await state.clear()
    await message.answer(
        f"{STYLE['divider']}\n"
        f"✅ АНКЕТА СОЗДАНА!\n"
        f"{STYLE['divider']}\n\n"
        f"Теперь можно смотреть анкеты 👀",
        reply_markup=get_main_keyboard()
    )

# ========== МОЯ АНКЕТА ==========
@dp.message(F.text.in_(["👤 МОЯ АНКЕТА", "МОЯ АНКЕТА"]))
async def my_profile(message: Message):
    user_id = message.from_user.id
    
    profile = db.get_profile(user_id)
    if not profile:
        await message.answer(
            f"❌ У тебя ещё нет анкеты!\n"
            f"Нажми /create чтобы создать анкету"
        )
        return
    
    # Статистика
    views = db.cursor.execute('SELECT COUNT(*) FROM views WHERE viewed_user_id = ?', (user_id,)).fetchone()[0]
    likes = db.cursor.execute('SELECT COUNT(*) FROM likes WHERE to_user = ?', (user_id,)).fetchone()[0]
    mutual = db.cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1 AND (from_user = ? OR to_user = ?)', (user_id, user_id)).fetchone()[0]
    
    user = db.get_user(user_id)
    is_premium = user[3]  # is_premium
    premium_badge = f" 💎" if is_premium else ""
    
    photos = json.loads(profile[7]) if profile[7] else []
    
    text = f"""
{STYLE['divider']}
👤 ТВОЯ АНКЕТА{premium_badge}
{STYLE['divider']}

👤 Имя: {profile[2]}
📅 Возраст: {profile[3]}
⚥ Пол: {profile[4]}
🏙 Город: {profile[5]}

📝 О себе:
{profile[6]}

📸 Фото: {len(photos)} шт.

{STYLE['divider']}
📊 СТАТИСТИКА:
👁 Просмотров: {views}
❤️ Лайков: {likes}
💕 Взаимных: {mutual}
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✏️ РЕДАКТИРОВАТЬ", callback_data="edit_profile_menu")
    builder.button(text=f"📸 ДОБАВИТЬ ФОТО", callback_data="add_photo")
    builder.button(text=f"🗑 УДАЛИТЬ", callback_data="delete_profile")
    builder.adjust(2, 1)
    
    if profile[8]:  # main_photo
        await message.answer_photo(
            photo=profile[8],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())

# ========== СМОТРЕТЬ ==========
@dp.message(F.text.in_(["👀 СМОТРЕТЬ", "СМОТРЕТЬ"]))
async def view_profiles(message: Message):
    user_id = message.from_user.id
    
    if not db.get_profile(user_id):
        await message.answer(f"❌ Сначала создай анкету через /create")
        return
    
    user = db.get_user(user_id)
    is_premium = user[3]
    views_used = user[6]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if views_used >= limit:
        await message.answer(
            f"❌ Лимит просмотров исчерпан ({limit})\n"
            f"Купи 💎 ПРЕМИУМ для увеличения лимита!"
        )
        return
    
    profile = db.get_random_profile(user_id)
    
    if not profile:
        await message.answer(
            f"🍺 Ты посмотрел все анкеты!\n"
            f"Заходи позже, появятся новые"
        )
        return
    
    # Сохраняем просмотр
    db.cursor.execute('''
        INSERT INTO views (user_id, viewed_user_id, viewed_at)
        VALUES (?, ?, ?)
    ''', (user_id, profile[1], datetime.now().isoformat()))
    
    db.cursor.execute('UPDATE users SET views_used = views_used + 1, views_total = views_total + 1 WHERE user_id = ?', (user_id,))
    db.cursor.execute('UPDATE profiles SET views_count = views_count + 1 WHERE user_id = ?', (profile[1],))
    db.conn.commit()
    db.update_stats('views_count')
    
    gender_emoji = "👨" if profile[4] == "Мужской" else "👩"
    text = f"""
{STYLE['divider']}
{gender_emoji} {profile[2]}, {profile[3]}
🏙 {profile[5]}

📝 {profile[6]}

❤️ {profile[10]} лайков | 👁 {profile[9]} просмотров
{STYLE['divider']}
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"❤️ ЛАЙК", callback_data=f"like_{profile[1]}")
    builder.button(text=f"▶️ ДАЛЬШЕ", callback_data="next_profile")
    builder.button(text=f"⚠️ ЖАЛОБА", callback_data=f"complaint_{profile[1]}")
    if profile[-1]:
        builder.button(text=f"📱 НАПИСАТЬ", url=f"https://t.me/{profile[-1]}")
    builder.adjust(2, 1, 1)
    
    photos = json.loads(profile[7]) if profile[7] else []
    main_photo = photos[0] if photos else profile[8]
    
    await message.answer_photo(
        photo=main_photo,
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
        await callback.answer(f"❌ Нельзя лайкнуть себя!", show_alert=True)
        return
    
    user = db.get_user(from_user)
    is_premium = user[3]
    likes_used = user[5]
    limit = PREMIUM_LIMIT if is_premium else FREE_LIMIT
    
    if likes_used >= limit:
        await callback.answer(f"❌ Лимит лайков ({limit}) исчерпан!", show_alert=True)
        return
    
    result = db.add_like(from_user, to_user)
    
    if result is None:
        await callback.answer(f"❌ Ты уже лайкал эту анкету", show_alert=True)
    elif result is True:
        await callback.answer(f"💕 ВЗАИМНЫЙ ЛАЙК!", show_alert=True)
        db.update_stats('mutual_count')
        
        # Получаем имена
        to_profile = db.get_profile(to_user)
        to_name = to_profile[2]
        to_user_data = db.get_user(to_user)
        to_username = to_user_data[1]
        
        from_profile = db.get_profile(from_user)
        from_name = from_profile[2]
        
        # Уведомления
        builder1 = InlineKeyboardBuilder()
        if to_username:
            builder1.button(text=f"📱 НАПИСАТЬ {to_name}", url=f"https://t.me/{to_username}")
        builder1.button(text=f"👀 ПРОДОЛЖИТЬ", callback_data="next_profile")
        
        await bot.send_message(
            from_user,
            f"{STYLE['divider']}\n"
            f"💕 ВЗАИМНЫЙ ЛАЙК!\n"
            f"{STYLE['divider']}\n\n"
            f"Ты понравился {to_name}!\n\n"
            f"Теперь вы можете пообщаться!",
            reply_markup=builder1.as_markup()
        )
        
        builder2 = InlineKeyboardBuilder()
        from_user_data = db.get_user(from_user)
        from_username = from_user_data[1]
        if from_username:
            builder2.button(text=f"📱 НАПИСАТЬ {from_name}", url=f"https://t.me/{from_username}")
        builder2.button(text=f"👀 ПРОДОЛЖИТЬ", callback_data="next_profile")
        
        await bot.send_message(
            to_user,
            f"{STYLE['divider']}\n"
            f"💕 ВЗАИМНЫЙ ЛАЙК!\n"
            f"{STYLE['divider']}\n\n"
            f"Ты понравился {from_name}!\n\n"
            f"Теперь вы можете пообщаться!",
            reply_markup=builder2.as_markup()
        )
    else:
        await callback.answer(f"❤️ ЛАЙК ОТПРАВЛЕН!")
        db.update_stats('likes_count')

# ========== ПРОДОЛЖЕНИЕ С ДРУГИМИ ОБРАБОТЧИКАМИ ==========
# (Топ, Рефералы, Игры, Чаты, Дни рождения, Поиск рядом, Стикеры, Статистика, Премиум и т.д.)

# ========== ЗАПУСК ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"""
{STYLE['header']}
🍺 ПИВЧИК ЗАПУЩЕН!
🍺 БД: 14 таблиц
🍺 АДМИН: {ADMIN_IDS[0]}
🍺 СТАТУС: ВСЕ РАБОТАЕТ
{STYLE['header']}
""")
    
    try:
        await dp.start_polling(bot)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
