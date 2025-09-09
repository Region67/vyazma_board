# database.py
import sqlite3
from typing import List, Tuple, Any, Optional

def init_db():
    """Создает таблицы объявлений и находок, если их еще нет."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()

    # Создание таблицы объявлений
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

    # Создание таблицы для "Потеряшек"
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS finds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            find_type TEXT NOT NULL, -- 'found' или 'lost'
            item TEXT NOT NULL,      -- Описание предмета
            description TEXT NOT NULL, -- Детали
            location TEXT NOT NULL,   -- Место
            date TEXT NOT NULL,       -- Дата события
            contact TEXT NOT NULL,    -- Контакт
            created_at TEXT NOT NULL  -- Дата создания записи
        )
    ''')

    conn.commit()
    conn.close()

# --- Функции для работы с "Объявлениями" (ads) ---
def add_ad(user_id: int, category: str, title: str, description: str, photo_ids: List[str], contact: str, created_at: str):
    """Добавляет новое объявление в базу данных."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ads (user_id, category, title, description, photo_ids, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, category, title, description, ','.join(photo_ids) if photo_ids else None, contact, created_at))
    conn.commit()
    conn.close()

def get_all_ads() -> List[Tuple[Any, ...]]:
    """Получает все объявления, отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_ad(ad_id: int):
    """Удаляет объявление по его ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ads WHERE id = ?', (ad_id,))
    conn.commit()
    conn.close()

def get_ad_by_id(ad_id: int) -> Optional[Tuple[Any, ...]]:
    """Получает одно объявление по его ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads WHERE id = ?', (ad_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_ads_by_category(category: str) -> List[Tuple[Any, ...]]:
    """Получает все объявления из указанной категории, отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads WHERE category = ? ORDER BY id DESC', (category,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_ads_by_user_id(user_id: int) -> List[Tuple[Any, ...]]:
    """Получает все объявления, созданные указанным пользователем, отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_ad_field(ad_id: int, field_name: str, new_value: str):
    """
    Обновляет значение конкретного поля объявления.
    field_name должно соответствовать имени столбца в БД: 'title', 'description', 'contact'.
    """
    # Сопоставление названий полей в коде с названиями в БД для безопасности
    db_field_map = {
        "title": "title",
        "description": "description",
        "contact": "contact"
        # Категорию и фото пока не редактируем через эту функцию
    }

    db_field = db_field_map.get(field_name)
    if not db_field:
        raise ValueError(f"Недопустимое имя поля для обновления: {field_name}")

    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    # Используем f-string для имени поля, так как его невозможно передать как параметр в execute
    # Это безопасно, потому что мы проверили значение `db_field` выше.
    query = f"UPDATE ads SET {db_field} = ? WHERE id = ?"
    cursor.execute(query, (new_value, ad_id))
    conn.commit()
    conn.close()

# --- Функции для работы с "Потеряшками" (finds) ---

def add_find(user_id: int, find_type: str, item: str, description: str, location: str, date: str, contact: str, created_at: str):
    """Добавляет новую запись о находке или потере."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO finds (user_id, find_type, item, description, location, date, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, find_type, item, description, location, date, contact, created_at))
    conn.commit()
    conn.close()

def get_finds_by_type(find_type: str) -> list:
    """Получает все записи указанного типа ('found' или 'lost'), отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM finds WHERE find_type = ? ORDER BY id DESC', (find_type,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_find_by_id(find_id: int) -> tuple or None:
    """Получает одну запись по её ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM finds WHERE id = ?', (find_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_finds_by_user_id(user_id: int) -> list:
    """Получает все записи, созданные указанным пользователем, отсортированные по ID (новые первые)."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM finds WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_find(find_id: int):
    """Удаляет запись по её ID."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM finds WHERE id = ?', (find_id,))
    conn.commit()
    conn.close()

def update_find_field(find_id: int, field_name: str, new_value: str):
    """
    Обновляет значение конкретного поля записи.
    field_name должно соответствовать имени столбца в БД: 'item', 'description', 'location', 'date', 'contact'.
    """
    # Сопоставление названий полей в коде с названиями в БД для безопасности
    db_field_map = {
        "item": "item",
        "description": "description",
        "location": "location",
        "date": "date",
        "contact": "contact"
        # find_type пока не редактируем
    }

    db_field = db_field_map.get(field_name)
    if not db_field:
        raise ValueError(f"Недопустимое имя поля для обновления в 'finds': {field_name}")

    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    # Используем f-string для имени поля, так как его невозможно передать как параметр в execute
    # Это безопасно, потому что мы проверили значение `db_field` выше.
    query = f"UPDATE finds SET {db_field} = ? WHERE id = ?"
    cursor.execute(query, (new_value, find_id))
    conn.commit()
    conn.close()

# Инициализация БД при импорте модуля (не обязательно, но удобно)
init_db()
