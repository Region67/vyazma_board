# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import asyncio
import logging

import config
import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
database.init_db()

# Храним фото временно
user_photos = {}

# Клавиатуры
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Подать объявление")],
        [KeyboardButton(text="🔍 Все объявления")],
        [KeyboardButton(text="🔍 Поиск по категориям")]
    ],
    resize_keyboard=True
)

categories_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🚗 Транспорт")],
        [KeyboardButton(text="💼 Работа/Услуги")],
        [KeyboardButton(text="🛒 Вещи")],
        [KeyboardButton(text="🐶 Отдам даром")],
        [KeyboardButton(text="🎓 Обучение")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для выбора категории поиска
search_categories_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🚗 Транспорт")],
        [KeyboardButton(text="💼 Работа/Услуги")],
        [KeyboardButton(text="🛒 Вещи")],
        [KeyboardButton(text="🐶 Отдам даром")],
        [KeyboardButton(text="🎓 Обучение")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Состояния
class AdStates(StatesGroup):
    category = State()
    title = State()
    description = State()
    photo = State()
    contact = State()
    search_category = State()  # Новое состояние для поиска

# Инициализация бота
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# /start
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "📢 Добро пожаловать в [Город] Объявления!\nВыберите действие:",
        reply_markup=main_menu
    )

# Подать объявление
@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    await message.answer("Выберите категорию:", reply_markup=categories_kb)
    await state.set_state(AdStates.category)

# Категория
@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
        return
    await state.update_data(category=message.text)
    await message.answer("Введите заголовок объявления:")
    await state.set_state(AdStates.title)

# Заголовок
@dp.message(StateFilter(AdStates.title))
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления:")
    await state.set_state(AdStates.description)

# Описание
@dp.message(StateFilter(AdStates.description))
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    user_photos[message.from_user.id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). Когда закончите — отправьте любой текст.")
    await state.set_state(AdStates.photo)

# Фото
@dp.message(StateFilter(AdStates.photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if len(user_photos[user_id]) < 3:
        user_photos[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos[user_id])}/3)")
        # Добавляем небольшую паузу для предотвращения флуда
        await asyncio.sleep(0.1)
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

# Когда пользователь отправляет текст вместо фото — переходим к контакту
@dp.message(StateFilter(AdStates.photo))
async def process_photo_done(message: Message, state: FSMContext):
    await message.answer("Введите контакт (телефон, @username или слово 'через бота'):")
    await state.set_state(AdStates.contact)

# Контакт
@dp.message(StateFilter(AdStates.contact))
async def process_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    photo_ids = user_photos.get(user_id, [])
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    database.add_ad(
        user_id=user_id,
        category=data['category'],
        title=data['title'],
        description=data['description'],
        photo_ids=photo_ids,
        contact=message.text,
        created_at=created_at
    )

    await message.answer("✅ Объявление успешно опубликовано!", reply_markup=main_menu)
    await state.clear()
    if user_id in user_photos:
        del user_photos[user_id]

# Все объявления
@dp.message(F.text == "🔍 Все объявления")
async def show_ads(message: Message):
    try:
        ads = database.get_all_ads()
        if not ads:
            await message.answer("Пока нет объявлений.", reply_markup=main_menu)
            return
        
        await message.answer("Последние объявления:", reply_markup=main_menu)
        
        for i, ad in enumerate(ads[:5]):  # Ограничиваем 5 объявлениями
            text = f"""
📌 {ad[3]}
{ad[4]}

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
            """
            await message.answer(text)
            photo_ids = ad[5]
            if photo_ids:
                photo_list = photo_ids.split(',')
                # Ограничиваем количество фото до 10 (предел Telegram для группы)
                media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                try:
                    await bot.send_media_group(chat_id=message.chat.id, media=media)
                except Exception as e:
                    logging.error(f"Ошибка при отправке фото: {e}")
                
                # Пауза между отправкой фото
                await asyncio.sleep(0.5)
            
            # Пауза между объявлениями
            if i < len(ads[:5]) - 1:  # Не делать паузу после последнего
                await asyncio.sleep(0.5)
                
    except Exception as e:
        logging.error(f"Ошибка в show_ads: {e}")
        await message.answer("Произошла ошибка при загрузке объявлений. Попробуйте позже.", reply_markup=main_menu)

# Поиск по категориям - кнопка
@dp.message(F.text == "🔍 Поиск по категориям")
async def search_by_category_start(message: Message, state: FSMContext):
    await message.answer("Выберите категорию для поиска:", reply_markup=search_categories_kb)
    await state.set_state(AdStates.search_category)

# Обработка выбора категории для поиска
@dp.message(StateFilter(AdStates.search_category))
async def process_search_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
        return
    
    category = message.text
    await state.update_data(search_category=category)
    
    try:
        # Получаем объявления по категории
        ads = database.get_ads_by_category(category)
        
        if not ads:
            await message.answer(f"Пока нет объявлений в категории '{category}'.", reply_markup=main_menu)
            await state.clear()
            return
        
        await message.answer(f"Объявления в категории '{category}':", reply_markup=main_menu)
        
        for i, ad in enumerate(ads[:5]):  # Показываем максимум 5 объявлений
            text = f"""
📌 {ad[3]}
{ad[4]}

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
            """
            await message.answer(text)
            photo_ids = ad[5]
            if photo_ids:
                photo_list = photo_ids.split(',')
                # Ограничиваем количество фото до 10
                media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                try:
                    await bot.send_media_group(chat_id=message.chat.id, media=media)
                except Exception as e:
                    logging.error(f"Ошибка при отправке фото: {e}")
                
                # Пауза между отправкой фото
                await asyncio.sleep(0.5)
            
            # Пауза между объявлениями
            if i < len(ads[:5]) - 1:  # Не делать паузу после последнего
                await asyncio.sleep(0.5)
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка в process_search_category: {e}")
        await message.answer("Произошла ошибка при поиске объявлений. Попробуйте позже.", reply_markup=main_menu)
        await state.clear()

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
