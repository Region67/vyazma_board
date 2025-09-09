# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import asyncio
import logging

import config from aiogram.filters import CommandObject
import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
database.init_db()

# Храним фото временно
user_photos = {}

# --- Клавиатуры ---
# Главное меню (без "Все объявления")
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Подать объявление")],
        [KeyboardButton(text="🔍 Все объявления")]
    ],
    resize_keyboard=True
)

# Список категорий
categories_list = [
    "🏠 Недвижимость", "🚗 Транспорт",
    "💼 Работа/Услуги", "🛒 Вещи",
    "🐶 Отдам даром", "🎓 Обучение"
]

# Создание клавиатуры категорий в 2 столбца
def create_categories_keyboard():
    categories_kb_rows = []
    for i in range(0, len(categories_list), 2):
        row = [KeyboardButton(text=cat) for cat in categories_list[i:i+2]]
        categories_kb_rows.append(row)
    categories_kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=categories_kb_rows, resize_keyboard=True)

# Используем функцию для создания клавиатур
categories_kb = create_categories_keyboard()
search_categories_kb = create_categories_keyboard() # Та же клавиатура для поиска

# --- Состояния ---
class AdStates(StatesGroup):
    category = State()
    title = State()
    description = State()
    photo = State()
    contact = State()
    search_category = State()
    admin_menu = State()
    admin_delete = State()

# --- Инициализация бота ---
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "📢 Добро пожаловать в Объявления города Вязьма!\nВыберите действие:",
        reply_markup=main_menu
    )
# Админка
@dp.message(Command("admin"))
async def admin_start(message: Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return
    
    # Если передан ID объявления для удаления
    if command.args and command.args.isdigit():
        ad_id = int(command.args)
        ad = database.get_ad_by_id(ad_id)
        if ad:
            database.delete_ad(ad_id)
            await message.answer(f"✅ Объявление #{ad_id} удалено!")
        else:
            await message.answer("❌ Объявление не найдено.")
        return

    await message.answer("🔧 Админ-панель\nВведите /admin_list для просмотра всех объявлений")    

@dp.message(Command("admin_list"))
async def admin_list(message: Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return

    ads = database.get_all_ads()
    if not ads:
        await message.answer("📭 Нет объявлений.")
        return

    await message.answer("📄 Все объявления:")

    for ad in ads[:10]:  # Показываем первые 10
        text = f"""
🆔 ID: {ad[0]}
📌 {ad[3]}
{ad[4][:100]}...

📅 {ad[7]}
/delete_{ad[0]} - Удалить
        """
        await message.answer(text)

# Обработка кнопок удаления
@dp.message(lambda message: message.text and message.text.startswith("/delete_"))
async def delete_ad_handler(message: Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return

    try:
        ad_id = int(message.text.split("_")[1])
        ad = database.get_ad_by_id(ad_id)
        if ad:
            database.delete_ad(ad_id)
            await message.answer(f"✅ Объявление #{ad_id} удалено!")
        else:
            await message.answer("❌ Объявление не найдено.")
    except:
        await message.answer("❌ Неверный формат команды.")

@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    await message.answer("Выберите категорию:", reply_markup=categories_kb)
    await state.set_state(AdStates.category)

@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
        return
    if message.text not in categories_list:
        await message.answer("Пожалуйста, выберите категорию из списка 👇.", reply_markup=categories_kb)
        return

    await state.update_data(category=message.text)
    # Скрываем клавиатуру категорий
    await message.answer("Введите заголовок объявления: ✅", reply_markup=main_menu)
    await state.set_state(AdStates.title)

@dp.message(StateFilter(AdStates.title))
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления: 💬")
    await state.set_state(AdStates.description)

@dp.message(StateFilter(AdStates.description))
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    user_photos[message.from_user.id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — отправьте любой текст.")
    await state.set_state(AdStates.photo)

@dp.message(StateFilter(AdStates.photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if len(user_photos[user_id]) < 3:
        user_photos[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos[user_id])}/3)")
        await asyncio.sleep(0.1)
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message(StateFilter(AdStates.photo))
async def process_photo_done(message: Message, state: FSMContext):
    await message.answer("Введите контакт 📞(телефон, @username):")
    await state.set_state(AdStates.contact)

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

# --- Поиск по категориям ---
@dp.message(F.text == "🔍 Все объявления")
async def search_by_category_start(message: Message, state: FSMContext):
    await message.answer("Выберите категорию:", reply_markup=search_categories_kb)
    await state.set_state(AdStates.search_category)

@dp.message(StateFilter(AdStates.search_category))
async def process_search_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
        return

    # Проверяем, что выбрана категория из списка
    if message.text not in categories_list:
        await message.answer("Пожалуйста, выберите категорию из списка.", reply_markup=search_categories_kb)
        # Не очищаем состояние, чтобы пользователь мог выбрать снова
        return

    category = message.text
    # Не обязательно сохранять в state для однократного использования, но можно
    # await state.update_data(search_category=category)

    try:
        ads = database.get_ads_by_category(category)

        if not ads:
            # Используем main_menu для возврата в главное меню
            await message.answer(f"Пока нет объявлений в категории '{category}'.", reply_markup=main_menu)
            await state.clear()
            return

        # Отправляем сообщение, что начинаем показ, и показываем main_menu
        await message.answer(f"Объявления в категории '{category}':", reply_markup=main_menu)

        for i, ad in enumerate(ads[:5]):
            text = f"""
📌 {ad[3]}  # Заголовок
💬 {ad[4]}      # Описание

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
            """
            await message.answer(text)
            photo_ids = ad[5]
            if photo_ids:
                try:
                    photo_list = photo_ids.split(',')
                    media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]] # Ограничение Telegram
                    await bot.send_media_group(chat_id=message.chat.id, media=media)
                except Exception as e:
                    logging.error(f"Ошибка при отправке фото для объявления {ad[0]}: {e}")
                await asyncio.sleep(0.5) # Пауза между фото

            if i < len(ads[:5]) - 1:
                await asyncio.sleep(0.5) # Пауза между объявлениями

        await state.clear() # Очищаем состояние после показа

    except Exception as e:
        logging.error(f"Ошибка в process_search_category: {e}")
        await message.answer("Произошла ошибка при поиске объявлений. Попробуйте позже.", reply_markup=main_menu)
        await state.clear()


# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
