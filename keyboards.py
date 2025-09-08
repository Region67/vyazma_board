# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("➕ Подать объявление"))
main_menu.add(KeyboardButton("🔍 Все объявления"))

categories_kb = ReplyKeyboardMarkup(resize_keyboard=True)
categories = ["🏠 Недвижимость", "🚗 Транспорт", "💼 Работа/Услуги", "🛒 Вещи", "🐶 Отдам даром", "🎓 Обучение"]
for cat in categories:
    categories_kb.add(KeyboardButton(cat))
categories_kb.add(KeyboardButton("⬅️ Назад"))
