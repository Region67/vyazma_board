# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, CommandObject
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

# --- Клавиатуры ---
# Список категорий
categories_list = [
    "🏠 Недвижимость", "🚗 Транспорт",
    "💼 Работа/Услуги", "🛒 Вещи",
    "🐶 Отдам даром", "🎓 Обучение"
]

# Создание клавиатуры категорий в 2 столбца с количеством объявлений
def create_categories_keyboard():
    categories_kb_rows = []
    for i in range(0, len(categories_list), 2):
        row_buttons = []
        for cat in categories_list[i:i+2]:
            # Получаем количество объявлений в этой категории
            # Убедись, что в database.py есть функция get_ads_by_category
            try:
                count = len(database.get_ads_by_category(cat))
            except Exception as e:
                logging.error(f"Ошибка при получении количества объявлений для категории '{cat}': {e}")
                count = 0
            row_buttons.append(KeyboardButton(text=f"{cat} ({count})"))
        categories_kb_rows.append(row_buttons)
    categories_kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=categories_kb_rows, resize_keyboard=True)

# Главное меню (создаётся динамически)
def create_main_menu():
    # Получаем общее количество объявлений
    try:
        total_ads_count = len(database.get_all_ads())
    except Exception as e:
        logging.error(f"Ошибка при получении общего количества объявлений: {e}")
        total_ads_count = 0

    main_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"➕ Подать объявление")],
            [KeyboardButton(text=f"🔍 Все объявления ({total_ads_count})")],
            [KeyboardButton(text="👤 Мои объявления")]
        ],
        resize_keyboard=True
    )
    return main_menu

# Используем функцию для создания клавиатур
# categories_kb и search_categories_kb создаются динамически при необходимости
# main_menu создаётся при запуске
main_menu = create_main_menu()

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
    # Новые состояния для "Мои объявления"
    my_ads_list = State()
    my_ad_selected = State()
    my_ad_edit_field = State() # Для выбора поля редактирования
    my_ad_edit_value = State() # Для ввода нового значения

# --- Инициализация бота ---
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: Message):
    # Обновляем главное меню при каждом запуске
    updated_main_menu = create_main_menu()
    await message.answer(
        "📢 Добро пожаловать в Объявления города Вязьма!\nВыберите действие:",
        reply_markup=updated_main_menu
    )

# --- Админка ---
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
            # Обновляем главное меню после удаления
            global main_menu
            main_menu = create_main_menu()
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

    try:
        ads = database.get_all_ads()
    except Exception as e:
        logging.error(f"Ошибка в admin_list: {e}")
        await message.answer("❌ Произошла ошибка при получении списка объявлений.")
        return

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
            # Обновляем главное меню после удаления
            global main_menu
            main_menu = create_main_menu()
            await message.answer(f"✅ Объявление #{ad_id} удалено!")
        else:
            await message.answer("❌ Объявление не найдено.")
    except Exception as e:
        logging.error(f"Ошибка в delete_ad_handler: {e}")
        await message.answer("❌ Неверный формат команды.")

# --- Подача объявления ---
@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    # Пересоздаем клавиатуру с актуальным количеством
    updated_kb = create_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=updated_kb)
    await state.set_state(AdStates.category)

@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Обновляем главное меню перед возвратом
        updated_main_menu = create_main_menu()
        await state.clear()
        await message.answer("Главное меню", reply_markup=updated_main_menu)
        return

    # Извлекаем название категории без количества "(...)"
    selected_category_text = message.text.split(" (")[0]
    if selected_category_text not in categories_list:
        updated_kb = create_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка 👇.", reply_markup=updated_kb)
        return

    await state.update_data(category=selected_category_text)
    # Скрываем клавиатуру категорий, показываем главное меню
    updated_main_menu = create_main_menu()
    await message.answer("Введите заголовок объявления: ✅", reply_markup=updated_main_menu)
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
        await asyncio.sleep(0.1) # Небольшая пауза
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

    try:
        database.add_ad(
            user_id=user_id,
            category=data['category'],
            title=data['title'],
            description=data['description'],
            photo_ids=photo_ids,
            contact=message.text,
            created_at=created_at
        )
        # Обновляем главное меню после добавления
        global main_menu
        main_menu = create_main_menu()
        await message.answer("✅ Объявление успешно опубликовано!", reply_markup=main_menu)
    except Exception as e:
        logging.error(f"Ошибка при добавлении объявления: {e}")
        updated_main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при публикации. Попробуйте позже.", reply_markup=updated_main_menu)

    await state.clear()
    if user_id in user_photos:
        del user_photos[user_id]

# --- Поиск по категориям ---
@dp.message(lambda message: message.text and message.text.startswith("🔍 Все объявления"))
async def search_by_category_start(message: Message, state: FSMContext):
    # Пересоздаем клавиатуру с актуальным количеством
    updated_kb = create_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=updated_kb)
    await state.set_state(AdStates.search_category)

@dp.message(StateFilter(AdStates.search_category))
async def process_search_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Обновляем главное меню перед возвратом
        updated_main_menu = create_main_menu()
        await state.clear()
        await message.answer("Главное меню", reply_markup=updated_main_menu)
        return

    # Извлекаем название категории без количества "(...)"
    selected_category_text = message.text.split(" (")[0]
    # Проверяем, что выбрана категория из списка
    if selected_category_text not in categories_list:
        updated_kb = create_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка.", reply_markup=updated_kb)
        return

    category = selected_category_text

    try:
        ads = database.get_ads_by_category(category)
    except Exception as e:
        logging.error(f"Ошибка в process_search_category: {e}")
        updated_main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при поиске объявлений. Попробуйте позже.", reply_markup=updated_main_menu)
        await state.clear()
        return

    if not ads:
        # Используем главное меню для возврата
        updated_main_menu = create_main_menu()
        await message.answer(f"📭 Пока нет объявлений в категории '{category}'.", reply_markup=updated_main_menu)
        await state.clear()
        return

    # Отправляем сообщение, что начинаем показ, и показываем главное меню
    updated_main_menu = create_main_menu()
    await message.answer(f"📄 Объявления в категории '{category}':", reply_markup=updated_main_menu)

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

# --- Мои объявления ---
@dp.message(F.text == "👤 Мои объявления")
async def my_ads_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        user_ads = database.get_ads_by_user_id(user_id) # Убедись, что эта функция есть в database.py
    except Exception as e:
        logging.error(f"Ошибка в my_ads_start: {e}")
        updated_main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при получении ваших объявлений.", reply_markup=updated_main_menu)
        return

    if not user_ads:
        updated_main_menu = create_main_menu()
        await message.answer("📭 У вас пока нет объявлений.", reply_markup=updated_main_menu)
        return

    await message.answer("📄 Ваши объявления:")
    # Сохраняем список объявлений пользователя в состоянии
    await state.update_data(my_ads=user_ads)
    await state.set_state(AdStates.my_ads_list)

    # Создаем клавиатуру с кнопками для каждого объявления
    kb = []
    for ad in user_ads[:10]: # Показываем первые 10
        button_text = f"🆔 {ad[0]}: {ad[3][:20]}..." # ID + заголовок
        kb.append([KeyboardButton(text=button_text)])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    ads_kb = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Выберите объявление для просмотра/редактирования/удаления:", reply_markup=ads_kb)

# Выбор конкретного объявления из списка "Мои объявления"
@dp.message(StateFilter(AdStates.my_ads_list))
async def my_ads_select(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Обновляем главное меню перед возвратом
        updated_main_menu = create_main_menu()
        await state.clear()
        await message.answer("Главное меню", reply_markup=updated_main_menu)
        return

    # Извлекаем ID из текста кнопки "🆔 123: Заголовок..."
    try:
        # Разбиваем по ":" и берем последний элемент первой части
        ad_id_str = message.text.split(":")[0].split()[-1]
        ad_id = int(ad_id_str)
        data = await state.get_data()
        user_ads = data.get('my_ads', [])
        selected_ad = next((ad for ad in user_ads if ad[0] == ad_id), None)

        if not selected_ad:
            await message.answer("❌ Объявление не найдено. Пожалуйста, выберите из списка.")
            return

        # Сохраняем выбранное объявление
        await state.update_data(selected_ad=selected_ad)
        await state.set_state(AdStates.my_ad_selected)

        # Отправляем информацию об объявлении
        text = f"""
🆔 ID: {selected_ad[0]}
📌 Категория: {selected_ad[2]}
🏷️ Заголовок: {selected_ad[3]}
📝 Описание: {selected_ad[4]}
📞 Контакт: {selected_ad[6]}
📅 Дата: {selected_ad[7]}
        """
        await message.answer(text)

        # Клавиатура с действиями
        actions_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Редактировать")],
                [KeyboardButton(text="🗑️ Удалить")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите действие:", reply_markup=actions_kb)

    except (ValueError, IndexError, StopIteration) as e:
        logging.error(f"Ошибка в my_ads_select: {e}")
        await message.answer("❌ Неверный формат. Пожалуйста, выберите объявление из списка.")

# --- Действия с выбранным объявлением ---
@dp.message(StateFilter(AdStates.my_ad_selected))
async def my_ad_action(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к списку объявлений
        await my_ads_start(message, state) # Повторно вызываем, чтобы обновить список
        return

    if message.text == "🗑️ Удалить":
        data = await state.get_data()
        selected_ad = data.get('selected_ad')
        if selected_ad:
            ad_id = selected_ad[0]
            try:
                database.delete_ad(ad_id)
                # Обновляем главное меню после удаления
                global main_menu
                main_menu = create_main_menu()
                updated_main_menu = create_main_menu()
                await message.answer(f"✅ Объявление #{ad_id} удалено!", reply_markup=updated_main_menu)
            except Exception as e:
                logging.error(f"Ошибка при удалении объявления #{ad_id}: {e}")
                updated_main_menu = create_main_menu()
                await message.answer("❌ Произошла ошибка при удалении.", reply_markup=updated_main_menu)
            await state.clear()
        else:
            updated_main_menu = create_main_menu()
            await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=updated_main_menu)
        return

    if message.text == "✏️ Редактировать":
        await state.set_state(AdStates.my_ad_edit_field)
        edit_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏷️ Заголовок")],
                [KeyboardButton(text="📝 Описание")],
                [KeyboardButton(text="📞 Контакт")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите поле для редактирования:", reply_markup=edit_kb)
        return

    await message.answer("Пожалуйста, выберите действие.")

# --- Выбор поля для редактирования ---
@dp.message(StateFilter(AdStates.my_ad_edit_field))
async def my_ad_edit_field(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к выбранному объявлению
        data = await state.get_data()
        selected_ad = data.get('selected_ad')
        if selected_ad:
            # Повторяем вывод объявления и действий
            text = f"""
🆔 ID: {selected_ad[0]}
📌 Категория: {selected_ad[2]}
🏷️ Заголовок: {selected_ad[3]}
📝 Описание: {selected_ad[4]}
📞 Контакт: {selected_ad[6]}
📅 Дата: {selected_ad[7]}
            """
            await message.answer(text)
            actions_kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✏️ Редактировать")],
                    [KeyboardButton(text="🗑️ Удалить")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer("Выберите действие:", reply_markup=actions_kb)
            await state.set_state(AdStates.my_ad_selected)
        else:
            updated_main_menu = create_main_menu()
            await message.answer("❌ Ошибка.", reply_markup=updated_main_menu)
        return

    field_map = {
        "🏷️ Заголовок": "title",
        "📝 Описание": "description",
        "📞 Контакт": "contact"
    }

    if message.text in field_map:
        field_name = field_map[message.text]
        await state.update_data(editing_field=field_name)
        await state.set_state(AdStates.my_ad_edit_value)

        data = await state.get_data()
        selected_ad = data.get('selected_ad')
        current_value = ""
        if selected_ad:
            if field_name == "title":
                current_value = selected_ad[3]
            elif field_name == "description":
                current_value = selected_ad[4]
            elif field_name == "contact":
                current_value = selected_ad[6]

        await message.answer(f"Введите новое значение для '{message.text}':\n(Текущее: {current_value})")
    else:
        await message.answer("Пожалуйста, выберите поле из списка.")

# --- Ввод нового значения ---
@dp.message(StateFilter(AdStates.my_ad_edit_value))
async def my_ad_edit_value(message: Message, state: FSMContext):
    new_value = message.text
    data = await state.get_data()
    selected_ad = data.get('selected_ad')
    field_name = data.get('editing_field')
    ad_id = selected_ad[0] if selected_ad else None

    if not selected_ad or not field_name or not ad_id:
        updated_main_menu = create_main_menu()
        await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=updated_main_menu)
        await state.clear()
        return

    # Обновляем в базе данных
    try:
        database.update_ad_field(ad_id, field_name, new_value) # Убедись, что эта функция есть в database.py
        # Обновляем главное меню после редактирования
        global main_menu
        main_menu = create_main_menu()
        updated_main_menu = create_main_menu()
        await message.answer(f"✅ Поле успешно обновлено!", reply_markup=updated_main_menu)

        # Очищаем состояние и возвращаемся в главное меню
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при обновлении поля: {e}")
        updated_main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при обновлении. Попробуйте позже.", reply_markup=updated_main_menu)
        await state.clear()

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
