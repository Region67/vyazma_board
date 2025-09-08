# database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            title TEXT,
            description TEXT,
            photo_ids TEXT,
            contact TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_ad(user_id, category, title, description, photo_ids, contact, created_at):
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ads (user_id, category, title, description, photo_ids, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, category, title, description, ','.join(photo_ids), contact, created_at))
    conn.commit()
    conn.close()

def get_all_ads():
    conn = sqlite3.connect('ads.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows
