# database.py (фрагмент - заменить существующие функции для 'finds')

# --- Функции для работы с "Потеряшками" (finds) ---
# Обновленная init_db для создания таблицы finds с photo_ids
def init_db():
    """Создает таблицы объявлений и находок, если их еще нет."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()

    # Создание таблицы объявлений (без изменений)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            photo_ids TEXT, -- Хранится как строка, разделенная запятыми
            contact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Создание/пересоздание таблицы для "Потеряшек" с поддержкой фото
    # ВНИМАНИЕ: Это удалит все старые записи в таблице 'finds'!
    # Если нужно сохранить данные, используйте ALTER TABLE вместо DROP.
    cursor.execute('DROP TABLE IF EXISTS finds') # Удалить старую таблицу
    cursor.execute('''
        CREATE TABLE finds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            find_type TEXT NOT NULL, -- 'found' или 'lost'
            item TEXT NOT NULL,      -- Описание предмета
            description TEXT NOT NULL, -- Детали
            location TEXT NOT NULL,   -- Место
            date TEXT NOT NULL,       -- Дата события
            contact TEXT NOT NULL,    -- Контакт
            photo_ids TEXT,           -- НОВОЕ: Хранится как строка, разделенная запятыми
            created_at TEXT NOT NULL  -- Дата создания записи
        )
    ''')

    conn.commit()
    conn.close()

# Обновленная функция добавления
def add_find(user_id: int, find_type: str, item: str, description: str, location: str, date: str, contact: str, photo_ids: list, created_at: str):
    """Добавляет новую запись о находке или потере с фото."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO finds (user_id, find_type, item, description, location, date, contact, photo_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, find_type, item, description, location, date, contact, ','.join(photo_ids) if photo_ids else None, created_at))
    conn.commit()
    conn.close()

# Обновленная функция получения по типу
def get_finds_by_type(find_type: str) -> list:
    """Получает все записи указанного типа ('found' или 'lost'), отсортированные по ID (новые первые)."""
    # Обновляем SELECT, чтобы включить photo_ids (теперь столбец 8, created_at - 9)
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, find_type, item, description, location, date, contact, photo_ids, created_at FROM finds WHERE find_type = ? ORDER BY id DESC', (find_type,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Обновленная функция получения по ID
def get_find_by_id(find_id: int) -> tuple or None:
    """Получает одну запись по её ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, find_type, item, description, location, date, contact, photo_ids, created_at FROM finds WHERE id = ?', (find_id,))
    row = cursor.fetchone()
    conn.close()
    return row

# Обновленная функция получения по user_id
def get_finds_by_user_id(user_id: int) -> list:
    """Получает все записи, созданные указанным пользователем, отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, find_type, item, description, location, date, contact, photo_ids, created_at FROM finds WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Функция удаления (без изменений, приведена для полноты)
def delete_find(find_id: int):
    """Удаляет запись по её ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM finds WHERE id = ?', (find_id,))
    conn.commit()
    conn.close()

# Функция обновления поля (без изменений, приведена для полноты)
def update_find_field(find_id: int, field_name: str, new_value: str):
    """
    Обновляет значение конкретного поля записи.
    field_name должно соответствовать имени столбца в БД: 'item', 'description', 'location', 'date', 'contact'.
    """
    db_field_map = {
        "item": "item",
        "description": "description",
        "location": "location",
        "date": "date",
        "contact": "contact"
    }

    db_field = db_field_map.get(field_name)
    if not db_field:
        raise ValueError(f"Недопустимое имя поля для обновления в 'finds': {field_name}")

    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    query = f"UPDATE finds SET {db_field} = ? WHERE id = ?"
    cursor.execute(query, (new_value, find_id))
    conn.commit()
    conn.close()

# ... (остальные функции для ads остаются без изменений)
