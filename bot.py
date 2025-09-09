# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from datetime import datetime
import asyncio
import logging

import config
import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
database.init_db()

# Храним фото временно (для объявлений)
user_photos = {}

# --- Клавиатуры ---
# Список категорий для объявлений
categories_list = [
    "🏠 Недвижимость", "🚗 Транспорт",
    "💼 Работа/Услуги", "🛒 Вещи",
    "🐶 Отдам даром", "🎓 Обучение"
]

# --- Функции для создания клавиатур ---
# Главное меню (разделы)
def create_main_sections_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Объявления")],
            [KeyboardButton(text="🔍 Потеряшки")],
            # [KeyboardButton(text="🎭 Афиша")] # Можно добавить позже
        ],
        resize_keyboard=True
    )

# Подменю "Объявления"
def create_ads_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Подать объявление")],
            [KeyboardButton(text="🔍 Поиск по категориям")],
            [KeyboardButton(text="👤 Мои объявления")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# Подменю "Потеряшки"
def create_finds_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Сообщить")], # Ведет к выбору "Найдено"/"Потеряно"
            [KeyboardButton(text="👀 Найдено")],   # Просмотр находок
            [KeyboardButton(text="🆘 Потеряно")], # Просмотр потерь
            [KeyboardButton(text="📝 Мои записи")], # Просмотр своих
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# Клавиатура выбора типа записи в "Потеряшках"
def create_find_type_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Нашел")],
            [KeyboardButton(text="😢 Потерял")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# Создание клавиатуры категорий в 2 столбца БЕЗ количества объявлений (для добавления)
def create_simple_categories_keyboard():
    categories_kb_rows = []
    for i in range(0, len(categories_list), 2):
        row = [KeyboardButton(text=cat) for cat in categories_list[i:i+2]]
        categories_kb_rows.append(row)
    categories_kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=categories_kb_rows, resize_keyboard=True)

# Создание клавиатуры категорий в 2 столбца С количеством объявлений (для поиска)
def create_search_categories_keyboard():
    categories_kb_rows = []
    for i in range(0, len(categories_list), 2):
        row_buttons = []
        for cat in categories_list[i:i+2]:
            # Получаем количество объявлений в этой категории
            try:
                count = len(database.get_ads_by_category(cat))
            except Exception as e:
                logging.error(f"Ошибка при получении количества объявлений для категории '{cat}': {e}")
                count = 0
            row_buttons.append(KeyboardButton(text=f"{cat} ({count})"))
        categories_kb_rows.append(row_buttons)
    categories_kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=categories_kb_rows, resize_keyboard=True)

# Клавиатура "Отмена/Назад" для скрытия меню во время ввода данных
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
    resize_keyboard=True
)

# Главное меню (счетчик обновляется при необходимости)
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

# --- Состояния для раздела "Потеряшки" ---
class FindStates(StatesGroup):
    # Выбор типа записи (найдено/потеряно) при добавлении
    choosing_type = State()
    # Ввод описания предмета
    entering_item = State()
    # Ввод описания деталей
    entering_description = State()
    # Ввод места
    entering_location = State()
    # Ввод даты
    entering_date = State()
    # Ввод контакта
    entering_contact = State()
    # Просмотр списка своих записей
    viewing_my_finds = State()
    # Выбор конкретной записи для действий
    viewing_selected_find = State()
    # Выбор действия (редактировать/удалить)
    choosing_action = State()
    # Выбор поля для редактирования
    choosing_edit_field = State()
    # Ввод нового значения при редактировании
    entering_edit_value = State()

# --- Инициализация бота ---
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: Message):
    # Очищаем состояние при входе в главное меню
    # await state.clear() # Не передается state в handler для Command
    main_sections_menu = create_main_sections_menu()
    await message.answer(
        "Добро пожаловать! Выберите раздел:",
        reply_markup=main_sections_menu
    )

# --- Навигация и главное меню ---
# --- Переход в раздел "Объявления" ---
@dp.message(F.text == "📢 Объявления")
async def enter_ads_section(message: Message, state: FSMContext):
    ads_submenu = create_ads_submenu()
    await message.answer("Раздел: Объявления", reply_markup=ads_submenu)

# --- Переход в раздел "Потеряшки" ---
@dp.message(F.text == "🔍 Потеряшки")
async def enter_finds_section(message: Message, state: FSMContext):
    finds_submenu = create_finds_submenu()
    await message.answer("Раздел: Потеряшки", reply_markup=finds_submenu)

# --- Кнопка "Назад" в главных разделах ---
# Для выхода из подменю "Объявления"
@dp.message(F.text == "⬅️ Назад", lambda msg: msg.reply_markup and any("Подать объявление" in row[0].text for row in msg.reply_markup.keyboard))
async def back_from_ads(message: Message, state: FSMContext):
    main_sections_menu = create_main_sections_menu()
    await state.clear() # Очищаем состояние, если нужно
    await message.answer("Главное меню", reply_markup=main_sections_menu)

# Для выхода из подменю "Потеряшки"
@dp.message(F.text == "⬅️ Назад", lambda msg: msg.reply_markup and any("Сообщить" in row[0].text for row in msg.reply_markup.keyboard))
async def back_from_finds(message: Message, state: FSMContext):
    main_sections_menu = create_main_sections_menu()
    await state.clear() # Очищаем состояние, если нужно
    await message.answer("Главное меню", reply_markup=main_sections_menu)

# --- Раздел "Объявления" ---
# --- Подача объявления ---
@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    # Используем УПРОЩЕННУЮ клавиатуру без количества
    simple_kb = create_simple_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=simple_kb)
    await state.set_state(AdStates.category)

@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Обновляем главное меню перед возвратом
        ads_submenu = create_ads_submenu()
        await state.clear()
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
        return

    # Проверяем по оригинальному списку, так как в кнопках нет количества
    if message.text not in categories_list:
        simple_kb = create_simple_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка 👇.", reply_markup=simple_kb)
        return

    await state.update_data(category=message.text)
    # Скрываем клавиатуру категорий, показываем клавиатуру "Отмена"
    await message.answer("Введите заголовок объявления: ✅", reply_markup=cancel_kb)
    await state.set_state(AdStates.title)

@dp.message(StateFilter(AdStates.title))
async def process_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
         # Возвращаемся к выбору категории
         await new_ad_start(message, state) # Повторно вызываем, чтобы показать клавиатуру категорий
         return

    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления: 💬", reply_markup=cancel_kb)
    await state.set_state(AdStates.description)

@dp.message(StateFilter(AdStates.description))
async def process_description(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к вводу заголовка
        data = await state.get_data()
        current_title = data.get('title', '')
        await message.answer(f"Введите заголовок объявления: ✅\n(Текущий: {current_title})", reply_markup=cancel_kb)
        await state.set_state(AdStates.title)
        return

    await state.update_data(description=message.text)
    user_photos[message.from_user.id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — отправьте любой текст.", reply_markup=cancel_kb)
    await state.set_state(AdStates.photo)

@dp.message(StateFilter(AdStates.photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    # if message.text == "⬅️ Назад": # Этот if не нужен здесь, так как это обработчик фото
    #     ...
    #     return

    user_id = message.from_user.id
    if len(user_photos[user_id]) < 3:
        user_photos[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos[user_id])}/3)")
        await asyncio.sleep(0.1) # Небольшая пауза
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message(StateFilter(AdStates.photo))
async def process_photo_done(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к загрузке фото (или к описанию, если фото уже есть)
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos.get(user_id, []))
        if photo_count > 0:
             await message.answer(f"Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — отправьте любой текст.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        else:
             # Если фото не было, возвращаемся к описанию
             current_desc = data.get('description', '')
             await message.answer(f"Введите описание объявления: 💬\n(Текущее: {current_desc[:50]}...)", reply_markup=cancel_kb)
             await state.set_state(AdStates.description)
        return

    await message.answer("Введите контакт 📞(телефон, @username):", reply_markup=cancel_kb)
    await state.set_state(AdStates.contact)

@dp.message(StateFilter(AdStates.contact))
async def process_contact(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к загрузке фото/завершению
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos.get(user_id, []))
        await message.answer(f"Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — отправьте любой текст.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        await state.set_state(AdStates.photo)
        return

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
        # global main_menu # Не используем global для reply_markup
        # main_menu = create_main_menu() # Не нужно обновлять тут, так как это другое меню
        ads_submenu = create_ads_submenu() # Возвращаем в подменю объявлений
        await message.answer("✅ Объявление успешно опубликовано!", reply_markup=ads_submenu)
    except Exception as e:
        logging.error(f"Ошибка при добавлении объявления: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при публикации. Попробуйте позже.", reply_markup=ads_submenu)

    await state.clear()
    if user_id in user_photos:
        del user_photos[user_id]

# --- Поиск по категориям ---
@dp.message(F.text == "🔍 Поиск по категориям")
async def search_by_category_start(message: Message, state: FSMContext):
    # Используем клавиатуру С количеством для поиска
    search_kb = create_search_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=search_kb)
    await state.set_state(AdStates.search_category)

@dp.message(StateFilter(AdStates.search_category))
async def process_search_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Обновляем подменю объявлений перед возвратом
        ads_submenu = create_ads_submenu()
        await state.clear()
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
        return

    # Извлекаем название категории без количества "(...)"
    selected_category_text = message.text.split(" (")[0]
    # Проверяем, что выбрана категория из списка
    if selected_category_text not in categories_list:
        search_kb = create_search_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка.", reply_markup=search_kb)
        return

    category = selected_category_text

    try:
        ads = database.get_ads_by_category(category)
    except Exception as e:
        logging.error(f"Ошибка в process_search_category: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при поиске объявлений. Попробуйте позже.", reply_markup=ads_submenu)
        await state.clear()
        return

    if not ads:
        # Используем подменю объявлений для возврата
        ads_submenu = create_ads_submenu()
        await message.answer(f"📭 Пока нет объявлений в категории '{category}'.", reply_markup=ads_submenu)
        await state.clear()
        return

    # Отправляем сообщение, что начинаем показ, и показываем подменю
    ads_submenu = create_ads_submenu()
    await message.answer(f"📄 Объявления в категории '{category}':", reply_markup=ads_submenu)

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
        user_ads = database.get_ads_by_user_id(user_id)
    except Exception as e:
        logging.error(f"Ошибка в my_ads_start: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при получении ваших объявлений.", reply_markup=ads_submenu)
        return

    if not user_ads:
        ads_submenu = create_ads_submenu()
        await message.answer("📭 У вас пока нет объявлений.", reply_markup=ads_submenu)
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
        # Обновляем подменю объявлений перед возвратом
        ads_submenu = create_ads_submenu()
        await state.clear()
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
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
                # Обновляем главное меню после удаления (не нужно, возвращаем в подменю)
                # global main_menu
                # main_menu = create_main_menu()
                ads_submenu = create_ads_submenu()
                await message.answer(f"✅ Объявление #{ad_id} удалено!", reply_markup=ads_submenu)
            except Exception as e:
                logging.error(f"Ошибка при удалении объявления #{ad_id}: {e}")
                ads_submenu = create_ads_submenu()
                await message.answer("❌ Произошла ошибка при удалении.", reply_markup=ads_submenu)
            await state.clear()
        else:
            ads_submenu = create_ads_submenu()
            await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=ads_submenu)
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
            ads_submenu = create_ads_submenu()
            await message.answer("❌ Ошибка.", reply_markup=ads_submenu)
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

        await message.answer(f"Введите новое значение для '{message.text}':\n(Текущее: {current_value})", reply_markup=cancel_kb)
    else:
        await message.answer("Пожалуйста, выберите поле из списка.")

# --- Ввод нового значения ---
@dp.message(StateFilter(AdStates.my_ad_edit_value))
async def my_ad_edit_value(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к выбору поля
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
        await state.set_state(AdStates.my_ad_edit_field)
        return

    new_value = message.text
    data = await state.get_data()
    selected_ad = data.get('selected_ad')
    field_name = data.get('editing_field')
    ad_id = selected_ad[0] if selected_ad else None

    if not selected_ad or not field_name or not ad_id:
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=ads_submenu)
        await state.clear()
        return

    # Обновляем в базе данных
    try:
        database.update_ad_field(ad_id, field_name, new_value)
        # Обновляем главное меню после редактирования (не нужно)
        # global main_menu
        # main_menu = create_main_menu()
        ads_submenu = create_ads_submenu()
        await message.answer(f"✅ Поле успешно обновлено!", reply_markup=ads_submenu)

        # Очищаем состояние и возвращаемся в подменю объявлений
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при обновлении поля: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при обновлении. Попробуйте позже.", reply_markup=ads_submenu)
        await state.clear()

# --- Раздел "Потеряшки" ---

# --- 1. Добавление записи ---
@dp.message(F.text == "➕ Сообщить")
async def finds_start_add(message: Message, state: FSMContext):
    find_type_kb = create_find_type_kb()
    await state.set_state(FindStates.choosing_type)
    await message.answer("Выберите тип записи:", reply_markup=find_type_kb)

# Обработка выбора типа
@dp.message(StateFilter(FindStates.choosing_type))
async def finds_process_type(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        finds_submenu = create_finds_submenu()
        await state.clear()
        await message.answer("Раздел: Потеряшки", reply_markup=finds_submenu)
        return
    if message.text not in ["🎁 Нашел", "😢 Потерял"]:
        find_type_kb = create_find_type_kb()
        await message.answer("Пожалуйста, выберите тип записи.", reply_markup=find_type_kb)
        return

    find_type = "found" if message.text == "🎁 Нашел" else "lost"
    await state.update_data(find_type=find_type)
    await state.set_state(FindStates.entering_item)
    await message.answer("Опишите предмет (например, 'Сумка', 'Ключи', 'Телефон'):", reply_markup=cancel_kb)

# Ввод предмета
@dp.message(StateFilter(FindStates.entering_item))
async def finds_process_item(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        find_type_kb = create_find_type_kb()
        await state.set_state(FindStates.choosing_type)
        await message.answer("Выберите тип записи:", reply_markup=find_type_kb)
        return
    await state.update_data(item=message.text)
    await state.set_state(FindStates.entering_description)
    await message.answer("Добавьте описание (цвет, марка, особые приметы):", reply_markup=cancel_kb)

# Ввод описания
@dp.message(StateFilter(FindStates.entering_description))
async def finds_process_description(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_item = data.get('item', '')
        await message.answer(f"Опишите предмет (например, 'Сумка', 'Ключи', 'Телефон'):\n(Текущий: {current_item})", reply_markup=cancel_kb)
        await state.set_state(FindStates.entering_item)
        return
    await state.update_data(description=message.text)
    await state.set_state(FindStates.entering_location)
    await message.answer("Где это было?", reply_markup=cancel_kb)

# Ввод места
@dp.message(StateFilter(FindStates.entering_location))
async def finds_process_location(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_desc = data.get('description', '')
        await message.answer(f"Добавьте описание (цвет, марка, особые приметы):\n(Текущее: {current_desc})", reply_markup=cancel_kb)
        await state.set_state(FindStates.entering_description)
        return
    await state.update_data(location=message.text)
    await state.set_state(FindStates.entering_date)
    await message.answer("Когда это было? (например, 'Сегодня утром', 'Вчера вечером')", reply_markup=cancel_kb)

# Ввод даты
@dp.message(StateFilter(FindStates.entering_date))
async def finds_process_date(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_loc = data.get('location', '')
        await message.answer(f"Где это было?\n(Текущее: {current_loc})", reply_markup=cancel_kb)
        await state.set_state(FindStates.entering_location)
        return
    await state.update_data(date=message.text)
    await state.set_state(FindStates.entering_contact)
    await message.answer("Контакт для связи (телефон, @username):", reply_markup=cancel_kb)

# Ввод контакта и сохранение
@dp.message(StateFilter(FindStates.entering_contact))
async def finds_process_contact_and_save(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_date = data.get('date', '')
        await message.answer(f"Когда это было? (например, 'Сегодня утром', 'Вчера вечером')\n(Текущее: {current_date})", reply_markup=cancel_kb)
        await state.set_state(FindStates.entering_date)
        return

    data = await state.get_data()
    user_id = message.from_user.id
    find_type = data['find_type']
    item = data['item']
    description = data['description']
    location = data['location']
    date = data['date']
    contact = message.text
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    try:
        database.add_find(
            user_id=user_id,
            find_type=find_type,
            item=item,
            description=description,
            location=location,
            date=date,
            contact=contact,
            created_at=created_at
        )
        finds_submenu = create_finds_submenu()
        await message.answer("✅ Запись успешно добавлена!", reply_markup=finds_submenu)
    except Exception as e:
        logging.error(f"Ошибка при добавлении записи в Потеряшки: {e}")
        finds_submenu = create_finds_submenu()
        await message.answer("❌ Произошла ошибка при добавлении записи. Попробуйте позже.", reply_markup=finds_submenu)

    await state.clear()

# --- 2. Просмотр записей ---
# --- Просмотр "Найдено" ---
@dp.message(F.text == "👀 Найдено")
async def finds_show_found(message: Message):
    try:
        found_items = database.get_finds_by_type("found")
        finds_submenu = create_finds_submenu()
        if not found_items:
            await message.answer("📭 Пока никто ничего не нашел.", reply_markup=finds_submenu)
            return

        await message.answer("🔍 Найдено:", reply_markup=finds_submenu)
        for item in found_items[:10]: # Показываем первые 10
             text = f"""
📌 Предмет: {item[3]}
📝 Описание: {item[4]}
📍 Где: {item[5]}
📅 Когда: {item[6]}
📞 Контакт: {item[7]}
🕒 Дата публикации: {item[8]}
             """
             await message.answer(text)
             await asyncio.sleep(0.1) # Минимальная пауза во избежание флуда
    except Exception as e:
        logging.error(f"Ошибка при показе найденных предметов: {e}")
        finds_submenu = create_finds_submenu()
        await message.answer("❌ Произошла ошибка при получении списка находок.", reply_markup=finds_submenu)

# --- Просмотр "Потеряно" ---
@dp.message(F.text == "🆘 Потеряно")
async def finds_show_lost(message: Message):
    try:
        lost_items = database.get_finds_by_type("lost")
        finds_submenu = create_finds_submenu()
        if not lost_items:
            await message.answer("📭 Пока никто ничего не потерял.", reply_markup=finds_submenu)
            return

        await message.answer("🆘 Потеряно:", reply_markup=finds_submenu)
        for item in lost_items[:10]: # Показываем первые 10
             text = f"""
📌 Предмет: {item[3]}
📝 Описание: {item[4]}
📍 Где: {item[5]}
📅 Когда: {item[6]}
📞 Контакт: {item[7]}
🕒 Дата публикации: {item[8]}
             """
             await message.answer(text)
             await asyncio.sleep(0.1) # Минимальная пауза во избежание флуда
    except Exception as e:
        logging.error(f"Ошибка при показе потерянных предметов: {e}")
        finds_submenu = create_finds_submenu()
        await message.answer("❌ Произошла ошибка при получении списка потерь.", reply_markup=finds_submenu)

# --- 3. Мои записи ---
# (Логика будет аналогична "Мои объявления", но для таблицы `finds`)
# ... (Можно реализовать позже по аналогии с `my_ads_start` и т.д.)

# --- Обработчики для "📝 Мои записи", редактирования и удаления ---
# ... (Можно реализовать позже)

# --- Админка (оставлена как в предыдущем коде) ---
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
            await message.answer(f"✅ Объявление #{ad_id} удалено!")
        else:
            await message.answer("❌ Объявление не найдено.")
    except Exception as e:
        logging.error(f"Ошибка в delete_ad_handler: {e}")
        await message.answer("❌ Неверный формат команды.")

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
