# database.py
import sqlite3
from typing import List, Tuple, Any, Optional

def init_db():
    """Создает таблицу объявлений, если её еще нет."""
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            photo_ids TEXT,
            contact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

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
    db_field_map = {
        "title": "title",
        "description": "description",
        "contact": "contact"
    }

    db_field = db_field_map.get(field_name)
    if not db_field:
        raise ValueError(f"Недопустимое имя поля для обновления: {field_name}")

    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    query = f"UPDATE ads SET {db_field} = ? WHERE id = ?"
    cursor.execute(query, (new_value, ad_id))
    conn.commit()
    conn.close()

# Инициализация БД при импорте модуля
init_db()
