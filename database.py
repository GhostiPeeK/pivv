import sqlite3
import json
from datetime import datetime
import random

class Database:
    def __init__(self, db_name="pivchik.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_all_tables()
        print("🍺 База данных ПИВЧИК подключена!")
    
    def create_all_tables(self):
        """Создание всех таблиц"""
        
        # ========== 1. ПОЛЬЗОВАТЕЛИ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'ru',
                
                -- Статус
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                is_admin INTEGER DEFAULT 0,
                
                -- Лимиты
                likes_used INTEGER DEFAULT 0,
                views_used INTEGER DEFAULT 0,
                likes_total INTEGER DEFAULT 0,
                views_total INTEGER DEFAULT 0,
                
                -- Баланс
                balance INTEGER DEFAULT 0,
                total_donated INTEGER DEFAULT 0,
                
                -- Рефералы
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                referral_earnings INTEGER DEFAULT 0,
                
                -- Гео
                city TEXT,
                country TEXT,
                latitude REAL,
                longitude REAL,
                
                -- Настройки
                notifications_enabled INTEGER DEFAULT 1,
                show_location INTEGER DEFAULT 0,
                show_age INTEGER DEFAULT 1,
                
                -- Даты
                joined_date TEXT,
                last_active TEXT,
                birth_date TEXT
            )
        ''')
        
        # ========== 2. АНКЕТЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                
                -- Основное
                name TEXT,
                age INTEGER,
                gender TEXT,
                city TEXT,
                about TEXT,
                
                -- Медиа
                main_photo TEXT,
                photos TEXT,  -- JSON массив
                
                -- Интересы
                interests TEXT,  -- JSON массив
                
                -- Статистика
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                mutual_count INTEGER DEFAULT 0,
                
                -- Статус
                is_active INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                
                -- Даты
                created_at TEXT,
                updated_at TEXT,
                
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 3. ЛАЙКИ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                created_at TEXT,
                is_mutual INTEGER DEFAULT 0,
                is_read INTEGER DEFAULT 0,
                UNIQUE(from_user, to_user),
                FOREIGN KEY (from_user) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (to_user) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 4. ПРОСМОТРЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                viewed_user_id INTEGER,
                viewed_at TEXT,
                UNIQUE(user_id, viewed_user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (viewed_user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 5. ЖАЛОБЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                on_user INTEGER,
                reason TEXT,
                description TEXT,
                created_at TEXT,
                status TEXT DEFAULT 'new',
                resolved_by INTEGER,
                resolved_at TEXT,
                FOREIGN KEY (from_user) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (on_user) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 6. РЕФЕРАЛЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                created_at TEXT,
                bonus_given INTEGER DEFAULT 0,
                bonus_amount INTEGER DEFAULT 50,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referred_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 7. ЧАТЫ ПО ИНТЕРЕСАМ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                interest TEXT,
                description TEXT,
                chat_link TEXT,
                created_at TEXT,
                members_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                joined_at TEXT,
                last_active TEXT,
                UNIQUE(chat_id, user_id),
                FOREIGN KEY (chat_id) REFERENCES chat_rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 8. ИГРЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER,
                user2_id INTEGER,
                game_type TEXT,
                status TEXT DEFAULT 'waiting',
                created_at TEXT,
                completed_at TEXT,
                winner_id INTEGER,
                user1_score INTEGER DEFAULT 0,
                user2_score INTEGER DEFAULT 0,
                game_data TEXT,  -- JSON с данными игры
                FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 9. ДНИ РОЖДЕНИЯ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                birth_date TEXT,
                birth_year INTEGER,
                zodiac TEXT,
                notifications_enabled INTEGER DEFAULT 1,
                last_notification TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 10. СТИКЕРЫ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                emoji TEXT,
                file_id TEXT,
                price INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_limited INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT -1,
                used_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sticker_id INTEGER,
                obtained_at TEXT,
                used_count INTEGER DEFAULT 0,
                UNIQUE(user_id, sticker_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (sticker_id) REFERENCES stickers(id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 11. ТРАНЗАКЦИИ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,  -- 'purchase', 'referral', 'bonus'
                description TEXT,
                payment_method TEXT,
                payment_id TEXT,
                status TEXT DEFAULT 'completed',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 12. ЛОГИ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                ip TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 13. АДМИН ЛОГИ ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_user INTEGER,
                details TEXT,
                created_at TEXT,
                FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # ========== 14. СТАТИСТИКА БОТА ==========
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                new_users INTEGER DEFAULT 0,
                new_profiles INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                mutual_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                messages_count INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                premium_purchases INTEGER DEFAULT 0,
                premium_income INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
        self.init_default_data()
    
    def init_default_data(self):
        """Инициализация начальных данных"""
        
        # Создаем чаты по интересам
        self.cursor.execute("SELECT COUNT(*) FROM chat_rooms")
        if self.cursor.fetchone()[0] == 0:
            chats = [
                ("🍺 Пивной ЧАТ", "🍺 Пиво", "Обсуждаем пиво и не только", None),
                ("🎵 Музыкальный ЧАТ", "🎵 Музыка", "Делимся треками и впечатлениями", None),
                ("🎮 Игровой ЧАТ", "🎮 Игры", "Общаемся об играх", None),
                ("🏋️ Спортивный ЧАТ", "🏋️ Спорт", "Тренировки, питание, мотивация", None),
                ("🎬 Кино ЧАТ", "🎬 Кино", "Обсуждаем фильмы и сериалы", None),
                ("📚 Книжный ЧАТ", "📚 Книги", "Читаем и обсуждаем", None),
                ("✈️ Путешествия ЧАТ", "✈️ Путешествия", "Советы, фото, истории", None),
                ("🐱 Животные ЧАТ", "🐱 Животные", "Для любителей питомцев", None)
            ]
            for chat in chats:
                self.cursor.execute('''
                    INSERT INTO chat_rooms (name, interest, description, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (chat[0], chat[1], chat[2], datetime.now().isoformat()))
        
        # Создаем стикеры
        self.cursor.execute("SELECT COUNT(*) FROM stickers")
        if self.cursor.fetchone()[0] == 0:
            stickers = [
                ("🍺 Пивной", "🍺", None, 0, 0, 0, -1),
                ("❤️ Сердечный", "❤️", None, 10, 0, 0, -1),
                ("💎 Премиум", "💎", None, 100, 1, 1, 100),
                ("🔥 Огонь", "🔥", None, 20, 0, 0, -1),
                ("🎁 Подарок", "🎁", None, 0, 0, 1, 50),
                ("👑 Корона", "👑", None, 50, 1, 0, -1),
                ("🍀 Удача", "🍀", None, 30, 0, 0, -1),
                ("⭐ Звезда", "⭐", None, 15, 0, 0, -1)
            ]
            for sticker in stickers:
                self.cursor.execute('''
                    INSERT INTO stickers (name, emoji, file_id, price, is_premium, is_limited, total_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (sticker[0], sticker[1], sticker[2], sticker[3], sticker[4], sticker[5], sticker[6], datetime.now().isoformat()))
        
        self.conn.commit()
    
    # ========== МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========
    
    def get_user(self, user_id):
        """Получить пользователя по ID"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def create_user(self, user_id, username, first_name):
        """Создать нового пользователя"""
        referral_code = f"PIV{user_id}{random.randint(1000, 9999)}"
        self.cursor.execute('''
            INSERT INTO users (user_id, username, first_name, joined_date, last_active, referral_code, balance)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat(), referral_code))
        self.conn.commit()
        return self.get_user(user_id)
    
    def update_last_active(self, user_id):
        """Обновить время последней активности"""
        self.cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                          (datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def update_user_city(self, user_id, city):
        """Обновить город пользователя"""
        self.cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (city, user_id))
        self.conn.commit()
    
    def add_balance(self, user_id, amount, description=""):
        """Добавить баланс пользователю"""
        self.cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        self.cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description, created_at)
            VALUES (?, ?, 'bonus', ?, ?)
        ''', (user_id, amount, description, datetime.now().isoformat()))
        self.conn.commit()
    
    # ========== МЕТОДЫ ДЛЯ АНКЕТ ==========
    
    def get_profile(self, user_id):
        """Получить анкету пользователя"""
        self.cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = 1', (user_id,))
        return self.cursor.fetchone()
    
    def create_profile(self, user_id, name, age, gender, city, about, photo):
        """Создать анкету"""
        photos = json.dumps([photo])
        self.cursor.execute('''
            INSERT INTO profiles (user_id, name, age, gender, city, about, main_photo, photos, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, age, gender, city, about, photo, photos, datetime.now().isoformat(), datetime.now().isoformat()))
        self.conn.commit()
    
    def update_profile(self, user_id, **kwargs):
        """Обновить поля анкеты"""
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(user_id)
        query = f"UPDATE profiles SET {', '.join(fields)}, updated_at = ? WHERE user_id = ?"
        self.cursor.execute(query, (*values, datetime.now().isoformat(), user_id))
        self.conn.commit()
    
    def add_photo(self, user_id, photo_id):
        """Добавить фото в анкету"""
        profile = self.get_profile(user_id)
        if profile:
            photos = json.loads(profile[7]) if profile[7] else []
            if len(photos) < 5:
                photos.append(photo_id)
                self.cursor.execute('UPDATE profiles SET photos = ?, updated_at = ? WHERE user_id = ?',
                                  (json.dumps(photos), datetime.now().isoformat(), user_id))
                self.conn.commit()
                return True
        return False
    
    def delete_profile(self, user_id):
        """Деактивировать анкету"""
        self.cursor.execute('UPDATE profiles SET is_active = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    # ========== МЕТОДЫ ДЛЯ ЛАЙКОВ ==========
    
    def add_like(self, from_user, to_user):
        """Добавить лайк"""
        try:
            self.cursor.execute('''
                INSERT INTO likes (from_user, to_user, created_at)
                VALUES (?, ?, ?)
            ''', (from_user, to_user, datetime.now().isoformat()))
            
            self.cursor.execute('UPDATE users SET likes_used = likes_used + 1, likes_total = likes_total + 1 WHERE user_id = ?', (from_user,))
            self.cursor.execute('UPDATE profiles SET likes_count = likes_count + 1 WHERE user_id = ?', (to_user,))
            self.conn.commit()
            
            # Проверяем взаимность
            self.cursor.execute('SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?', (to_user, from_user))
            if self.cursor.fetchone():
                self.cursor.execute('''
                    UPDATE likes SET is_mutual = 1 
                    WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                ''', (from_user, to_user, to_user, from_user))
                self.cursor.execute('UPDATE profiles SET mutual_count = mutual_count + 1 WHERE user_id IN (?, ?)', (from_user, to_user))
                self.conn.commit()
                return True  # Взаимный лайк
            return False  # Обычный лайк
        except sqlite3.IntegrityError:
            return None  # Уже лайкал
    
    # ========== МЕТОДЫ ДЛЯ РЕФЕРАЛОВ ==========
    
    def process_referral(self, referrer_code, new_user_id):
        """Обработать реферальный переход"""
        self.cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referrer_code,))
        referrer = self.cursor.fetchone()
        if referrer and referrer[0] != new_user_id:
            self.cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, created_at, bonus_amount)
                VALUES (?, ?, ?, 50)
            ''', (referrer[0], new_user_id, datetime.now().isoformat()))
            
            self.cursor.execute('''
                UPDATE users SET 
                    referral_count = referral_count + 1,
                    balance = balance + 50,
                    referral_earnings = referral_earnings + 50
                WHERE user_id = ?
            ''', (referrer[0],))
            
            self.cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (referrer[0], new_user_id))
            self.conn.commit()
            return referrer[0]
        return None
    
    # ========== МЕТОДЫ ДЛЯ СТАТИСТИКИ ==========
    
    def update_stats(self, stat_type, count=1):
        """Обновить статистику бота"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute(f'''
            INSERT INTO bot_stats (date, {stat_type}) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET {stat_type} = {stat_type} + ?
        ''', (today, count, count))
        self.conn.commit()
    
    # ========== МЕТОДЫ ДЛЯ ПОИСКА ==========
    
    def get_random_profile(self, user_id):
        """Получить случайную анкету для просмотра"""
        self.cursor.execute('''
            SELECT p.*, u.username FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id != ? 
            AND p.is_active = 1
            AND u.is_banned = 0
            AND p.user_id NOT IN (
                SELECT viewed_user_id FROM views WHERE user_id = ?
            )
            ORDER BY RANDOM()
            LIMIT 1
        ''', (user_id, user_id))
        return self.cursor.fetchone()
    
    def get_top_by_likes(self, limit=10):
        """Топ по лайкам"""
        self.cursor.execute('''
            SELECT u.user_id, p.name, p.likes_count, p.main_photo 
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.likes_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_top_by_views(self, limit=10):
        """Топ по просмотрам"""
        self.cursor.execute('''
            SELECT u.user_id, p.name, p.views_count, p.main_photo 
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.is_active = 1
            ORDER BY p.views_count DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def get_nearby_users(self, user_id, city):
        """Найти пользователей в том же городе"""
        self.cursor.execute('''
            SELECT u.user_id, p.name, p.age, p.gender, p.main_photo 
            FROM users u
            JOIN profiles p ON u.user_id = p.user_id
            WHERE u.city = ? AND u.user_id != ? AND p.is_active = 1
            ORDER BY RANDOM()
            LIMIT 5
        ''', (city, user_id))
        return self.cursor.fetchall()
    
    # ========== МЕТОДЫ ДЛЯ ДНЕЙ РОЖДЕНИЯ ==========
    
    def set_birthday(self, user_id, birth_date):
        """Установить день рождения"""
        from datetime import datetime
        birth = datetime.strptime(birth_date, "%d.%m.%Y")
        zodiac = self.get_zodiac(birth)
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO birthdays 
            (user_id, birth_date, birth_year, zodiac, notifications_enabled)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, birth_date, birth.year, zodiac))
        
        # Обновляем возраст в анкете
        age = (datetime.now() - birth).days // 365
        self.cursor.execute('UPDATE profiles SET age = ? WHERE user_id = ?', (age, user_id))
        self.conn.commit()
        return zodiac, age
    
    def get_zodiac(self, date):
        """Определить знак зодиака"""
        day, month = date.day, date.month
        if (month == 3 and day >= 21) or (month == 4 and day <= 19):
            return "♈ Овен"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
            return "♉ Телец"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
            return "♊ Близнецы"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
            return "♋ Рак"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
            return "♌ Лев"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
            return "♍ Дева"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
            return "♎ Весы"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
            return "♏ Скорпион"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
            return "♐ Стрелец"
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
            return "♑ Козерог"
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
            return "♒ Водолей"
        else:
            return "♓ Рыбы"
    
    def get_today_birthdays(self):
        """Получить именинников сегодня"""
        today = datetime.now().strftime("%m-%d")
        self.cursor.execute('''
            SELECT u.user_id, u.first_name, b.birth_date, b.zodiac 
            FROM birthdays b
            JOIN users u ON b.user_id = u.user_id
            WHERE strftime('%m-%d', b.birth_date) = ?
        ''', (today,))
        return self.cursor.fetchall()
    
    # ========== МЕТОДЫ ДЛЯ СТИКЕРОВ ==========
    
    def get_stickers(self, user_id):
        """Получить все стикеры с информацией о владении"""
        self.cursor.execute('''
            SELECT s.id, s.name, s.emoji, s.price, s.is_premium,
                   CASE WHEN us.id IS NOT NULL THEN 1 ELSE 0 END as owned
            FROM stickers s
            LEFT JOIN user_stickers us ON s.id = us.sticker_id AND us.user_id = ?
            ORDER BY s.is_premium, s.price
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def buy_sticker(self, user_id, sticker_id):
        """Купить стикер"""
        # Проверяем баланс
        self.cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT price, is_premium FROM stickers WHERE id = ?', (sticker_id,))
        sticker = self.cursor.fetchone()
        
        if balance < sticker[0]:
            return False, "Недостаточно средств"
        
        if sticker[1] == 1:
            self.cursor.execute('SELECT is_premium FROM users WHERE user_id = ?', (user_id,))
            is_premium = self.cursor.fetchone()[0]
            if not is_premium:
                return False, "Только для премиум"
        
        # Покупаем
        self.cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (sticker[0], user_id))
        self.cursor.execute('''
            INSERT INTO user_stickers (user_id, sticker_id, obtained_at)
            VALUES (?, ?, ?)
        ''', (user_id, sticker_id, datetime.now().isoformat()))
        
        self.cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description, created_at)
            VALUES (?, ?, 'purchase', ?, ?)
        ''', (user_id, -sticker[0], f"Покупка стикера {sticker_id}", datetime.now().isoformat()))
        
        self.conn.commit()
        return True, "Куплено"
    
    # ========== МЕТОДЫ ДЛЯ АДМИНОВ ==========
    
    def get_stats(self):
        """Получить общую статистику"""
        stats = {}
        
        self.cursor.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
        stats['premium_users'] = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM profiles WHERE is_active = 1')
        stats['active_profiles'] = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "new"')
        stats['new_complaints'] = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM likes WHERE is_mutual = 1')
        stats['mutual_likes'] = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT SUM(balance) FROM users')
        stats['total_balance'] = self.cursor.fetchone()[0] or 0
        
        return stats
    
    def get_daily_stats(self, days=7):
        """Получить статистику по дням"""
        self.cursor.execute('''
            SELECT * FROM bot_stats 
            ORDER BY date DESC LIMIT ?
        ''', (days,))
        return self.cursor.fetchall()
    
    def close(self):
        """Закрыть соединение"""
        self.conn.close()

# Создаем глобальный экземпляр БД
db = Database()
