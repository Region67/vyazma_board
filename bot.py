Хорошо, вот исправленный `bot.py` с улучшенной логикой отправки сообщений, чтобы избежать ошибки `TelegramRetryAfter` (флуд-контроль). Я добавил паузы между отправкой сообщений и уточнил обработку ошибок.

**Основные изменения:**

1.  **Добавлены паузы:** `await asyncio.sleep(0.5)` или `1` секунда добавлены между отправкой основных сообщений (объявлений, записей "Потеряшек") и между отправкой групп фото.
2.  **Уточнена обработка ошибок:** Добавлен импорт `aiogram.exceptions` и отдельная обработка `TelegramRetryAfter` в критических местах, чтобы пользователь получал более понятное сообщение.
3.  **Улучшена навигация:** Кнопка "⬅️ Назад" в подменю "Объявления" и "Потеряшки" теперь корректно возвращает в главное меню и очищает состояние.

**ВАЖНО:** Для этого кода требуется, чтобы `database.py` также был обновлён для поддержки `photo_ids` в таблице `finds`. Убедитесь, что вы используете последнюю версию `database.py`, которую я предоставлял ранее (с `import sqlite3` и обновлённой таблицей `finds`).

```python
# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import asyncio
import logging
# Импортируем исключения для точной обработки ошибок
import aiogram.exceptions

import config
import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
database.init_db()

# Храним фото временно
user_photos_ads = {}      # Для объявлений
user_photos_finds = {}    # Для потеряшек

# --- Константы ---
CATEGORIES_LIST = [
    "🏠 Недвижимость", "🚗 Транспорт",
    "💼 Работа/Услуги", "🛒 Вещи",
    "🐶 Отдам даром", "🎓 Обучение"
]

# --- Функции для создания клавиатур ---
def create_main_sections_menu():
    """Создает главное меню с разделами."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Объявления")],
            [KeyboardButton(text="🔍 Потеряшки")],
        ],
        resize_keyboard=True
    )

def create_ads_submenu():
    """Создает подменю для раздела Объявления."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Подать объявление"), KeyboardButton(text="🔍 Поиск по категориям")],
            [KeyboardButton(text="👤 Мои объявления")],
            [KeyboardButton(text="⬅️ Назад")], # Центрированная кнопка назад
        ],
        resize_keyboard=True
    )

def create_finds_submenu():
    """Создает подменю для раздела Потеряшки."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Сообщить"), KeyboardButton(text="👀 Найдено")],
            [KeyboardButton(text="🆘 Потеряно"), KeyboardButton(text="📝 Мои записи")],
            [KeyboardButton(text="⬅️ Назад")], # Центрированная кнопка назад
        ],
        resize_keyboard=True
    )

def create_find_type_kb():
    """Клавиатура выбора типа записи в Потеряшках."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Нашел"), KeyboardButton(text="😢 Потерял")],
            [KeyboardButton(text="⬅️ Назад")], # Центрированная кнопка назад
        ],
        resize_keyboard=True
    )

def create_simple_categories_keyboard():
    """Клавиатура категорий для добавления объявления (2 колонки)."""
    kb_rows = []
    for i in range(0, len(CATEGORIES_LIST), 2):
        row = [KeyboardButton(text=cat) for cat in CATEGORIES_LIST[i:i+2]]
        kb_rows.append(row)
    kb_rows.append([KeyboardButton(text="⬅️ Назад")]) # Центрированная кнопка назад
    return ReplyKeyboardMarkup(keyboard=kb_rows, resize_keyboard=True)

def create_search_categories_keyboard():
    """Клавиатура категорий для поиска объявлений (2 колонки с количеством)."""
    kb_rows = []
    for i in range(0, len(CATEGORIES_LIST), 2):
        row_buttons = []
        for cat in CATEGORIES_LIST[i:i+2]:
            try:
                count = len(database.get_ads_by_category(cat))
            except Exception as e:
                logging.error(f"Ошибка при подсчете объявлений для категории '{cat}': {e}")
                count = 0
            row_buttons.append(KeyboardButton(text=f"{cat} ({count})"))
        kb_rows.append(row_buttons)
    kb_rows.append([KeyboardButton(text="⬅️ Назад")]) # Центрированная кнопка назад
    return ReplyKeyboardMarkup(keyboard=kb_rows, resize_keyboard=True)

# Клавиатура "Отмена/Назад" для скрытия меню во время ввода данных
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад")]], # Центрированная кнопка назад
    resize_keyboard=True
)

# --- Состояния ---
class AdStates(StatesGroup):
    category = State()
    title = State()
    description = State()
    photo = State()
    contact = State()
    search_category = State()
    my_ads_list = State()
    my_ad_selected = State()
    my_ad_edit_field = State()
    my_ad_edit_value = State()

class FindStates(StatesGroup):
    choosing_type = State()
    entering_item = State()
    entering_description = State()
    entering_location = State()
    entering_date = State()
    entering_contact = State()
    uploading_photos = State() # Новое состояние для фото
    viewing_my_finds = State()
    viewing_selected_find = State()
    choosing_action = State()
    choosing_edit_field = State()
    entering_edit_value = State()

# --- Инициализация бота ---
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: Message):
    main_menu = create_main_sections_menu()
    await message.answer(
        "Добро пожаловать! Выберите раздел:",
        reply_markup=main_menu
    )

# --- Навигация и главное меню ---
@dp.message(F.text == "📢 Объявления")
async def enter_ads_section(message: Message, state: FSMContext):
    ads_submenu = create_ads_submenu()
    await message.answer("Раздел: Объявления", reply_markup=ads_submenu)

@dp.message(F.text == "🔍 Потеряшки")
async def enter_finds_section(message: Message, state: FSMContext):
    finds_submenu = create_finds_submenu()
    await message.answer("Раздел: Потеряшки", reply_markup=finds_submenu)

# --- Общая кнопка "Назад" для выхода в главное меню ---
@dp.message(F.text == "⬅️ Назад")
async def go_back_to_main(message: Message, state: FSMContext):
    # Очищаем состояние при выходе в главное меню
    await state.clear()
    # Удаляем временные данные пользователя, если есть
    user_id = message.from_user.id
    if user_id in user_photos_ads:
        del user_photos_ads[user_id]
    if user_id in user_photos_finds:
        del user_photos_finds[user_id]

    main_menu = create_main_sections_menu()
    await message.answer("Главное меню", reply_markup=main_menu)


# --- Раздел "Объявления" ---
@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    simple_kb = create_simple_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=simple_kb)
    await state.set_state(AdStates.category)

@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        ads_submenu = create_ads_submenu()
        await state.clear()
        user_id = message.from_user.id
        if user_id in user_photos_ads:
             del user_photos_ads[user_id]
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
        return

    if message.text not in CATEGORIES_LIST:
        simple_kb = create_simple_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка 👇.", reply_markup=simple_kb)
        return

    await state.update_data(category=message.text)
    await message.answer("Введите заголовок объявления: ✅", reply_markup=cancel_kb)
    await state.set_state(AdStates.title)

@dp.message(StateFilter(AdStates.title))
async def process_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
         await new_ad_start(message, state)
         return
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления: 💬", reply_markup=cancel_kb)
    await state.set_state(AdStates.description)

@dp.message(StateFilter(AdStates.description))
async def process_description(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_title = data.get('title', '')
        await message.answer(f"Введите заголовок объявления: ✅\n(Текущий: {current_title})", reply_markup=cancel_kb)
        await state.set_state(AdStates.title)
        return
    await state.update_data(description=message.text)
    user_id = message.from_user.id
    user_photos_ads[user_id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — нажмите 'Готово'.", reply_markup=cancel_kb)
    await state.set_state(AdStates.photo)

@dp.message(StateFilter(AdStates.photo), F.photo)
async def process_photo_ad(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_photos_ads:
        user_photos_ads[user_id] = []
    if len(user_photos_ads[user_id]) < 3:
        user_photos_ads[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos_ads[user_id])}/3)")
        await asyncio.sleep(0.1) # Минимальная пауза
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message(StateFilter(AdStates.photo))
async def process_photo_done_ad(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos_ads.get(user_id, []))
        if photo_count > 0:
             await message.answer(f"Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — нажмите 'Готово'.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        else:
             current_desc = data.get('description', '')
             await message.answer(f"Введите описание объявления: 💬\n(Текущее: {current_desc[:50]}...)", reply_markup=cancel_kb)
             await state.set_state(AdStates.description)
        return
    await message.answer("Введите контакт 📞(телефон, @username):", reply_markup=cancel_kb)
    await state.set_state(AdStates.contact)

@dp.message(StateFilter(AdStates.contact))
async def process_contact_ad(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos_ads.get(user_id, []))
        await message.answer(f"Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — нажмите 'Готово'.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        await state.set_state(AdStates.photo)
        return

    data = await state.get_data()
    user_id = message.from_user.id
    photo_ids = user_photos_ads.get(user_id, [])
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
        ads_submenu = create_ads_submenu()
        if user_id in user_photos_ads:
             del user_photos_ads[user_id]
        await message.answer("✅ Объявление успешно опубликовано!", reply_markup=ads_submenu)
    except Exception as e:
        logging.error(f"Ошибка при добавлении объявления: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при публикации. Попробуйте позже.", reply_markup=ads_submenu)

    await state.clear()

@dp.message(F.text == "🔍 Поиск по категориям")
async def search_by_category_start(message: Message, state: FSMContext):
    search_kb = create_search_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=search_kb)
    await state.set_state(AdStates.search_category)

@dp.message(StateFilter(AdStates.search_category))
async def process_search_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        ads_submenu = create_ads_submenu()
        await state.clear()
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
        return

    selected_category_text = message.text.split(" (")[0]
    if selected_category_text not in CATEGORIES_LIST:
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
        ads_submenu = create_ads_submenu()
        await message.answer(f"📭 Пока нет объявлений в категории '{category}'.", reply_markup=ads_submenu)
        await state.clear()
        return

    ads_submenu = create_ads_submenu()
    # Скрываем клавиатуру перед списком
    await message.answer(f"📄 Объявления в категории '{category}':", reply_markup=types.ReplyKeyboardRemove())

    for i, ad in enumerate(ads[:5]):
        text = f"""
📌 {ad[3]}
💬 {ad[4]}

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
        """
        try:
            await message.answer(text)
        except aiogram.exceptions.TelegramRetryAfter as e:
            logging.warning(f"Флуд-контроль при отправке текста объявления: {e}")
            await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
            await asyncio.sleep(e.retry_after)
            # Повторная попытка
            await message.answer(text)
        except Exception as e:
            logging.error(f"Другая ошибка при отправке текста объявления: {e}")
            await message.answer("❌ Ошибка при отправке объявления.")

        photo_ids = ad[5]
        if photo_ids:
            try:
                photo_list = photo_ids.split(',')
                media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                await bot.send_media_group(chat_id=message.chat.id, media=media)
                await asyncio.sleep(1) # Пауза после отправки фото
            except aiogram.exceptions.TelegramRetryAfter as e:
                logging.warning(f"Флуд-контроль при отправке фото: {e}")
                await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                await asyncio.sleep(e.retry_after)
                # Повторная попытка
                try:
                    await bot.send_media_group(chat_id=message.chat.id, media=media)
                    await asyncio.sleep(1)
                except Exception as e2:
                    logging.error(f"Ошибка при повторной отправке фото: {e2}")
            except Exception as e:
                logging.error(f"Ошибка при отправке фото для объявления {ad[0]}: {e}")

        # Пауза между объявлениями
        if i < len(ads[:5]) - 1:
            await asyncio.sleep(1)

    await message.answer("Поиск завершен.", reply_markup=ads_submenu)
    await state.clear()

@dp.message(F.text == "👤 Мои объявления")
async def my_ads_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        user_ads = database.get_ads_by_user_id(user_id)
    except Exception as e:
        logging.error(f"Ошибка в my_ads_start (получение из БД): {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при получении ваших объявлений.", reply_markup=ads_submenu)
        return

    if not user_ads:
        ads_submenu = create_ads_submenu()
        await message.answer("📭 У вас пока нет объявлений.", reply_markup=ads_submenu)
        return

    await message.answer("📄 Ваши объявления:", reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(my_ads=user_ads)
    await state.set_state(AdStates.my_ads_list)

    kb = []
    for ad in user_ads[:10]:
        button_text = f"🆔 {ad[0]}: {ad[3][:20]}..."
        kb.append([KeyboardButton(text=button_text)])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    ads_kb = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Выберите объявление для просмотра/редактирования/удаления:", reply_markup=ads_kb)

@dp.message(StateFilter(AdStates.my_ads_list))
async def my_ads_select(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        ads_submenu = create_ads_submenu()
        await state.clear()
        await message.answer("Раздел: Объявления", reply_markup=ads_submenu)
        return

    try:
        ad_id_str = message.text.split(":")[0].split()[-1]
        ad_id = int(ad_id_str)
        data = await state.get_data()
        user_ads = data.get('my_ads', [])
        selected_ad = next((ad for ad in user_ads if ad[0] == ad_id), None)

        if not selected_ad:
            await message.answer("❌ Объявление не найдено. Пожалуйста, выберите из списка.")
            return

        await state.update_data(selected_ad=selected_ad)
        await state.set_state(AdStates.my_ad_selected)

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
                [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="🗑️ Удалить")],
                [KeyboardButton(text="⬅️ Назад")],
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите действие:", reply_markup=actions_kb)

    except (ValueError, IndexError, StopIteration) as e:
        logging.error(f"Ошибка в my_ads_select: {e}")
        await message.answer("❌ Неверный формат. Пожалуйста, выберите объявление из списка.")

@dp.message(StateFilter(AdStates.my_ad_selected))
async def my_ad_action(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await my_ads_start(message, state)
        return

    if message.text == "🗑️ Удалить":
        data = await state.get_data()
        selected_ad = data.get('selected_ad')
        if selected_ad:
            ad_id = selected_ad[0]
            try:
                database.delete_ad(ad_id)
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
                [KeyboardButton(text="🏷️ Заголовок"), KeyboardButton(text="📝 Описание")],
                [KeyboardButton(text="📞 Контакт")],
                [KeyboardButton(text="⬅️ Назад")],
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите поле для редактирования:", reply_markup=edit_kb)
        return

    await message.answer("Пожалуйста, выберите действие.")

@dp.message(StateFilter(AdStates.my_ad_edit_field))
async def my_ad_edit_field(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        selected_ad = data.get('selected_ad')
        if selected_ad:
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
                    [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="🗑️ Удалить")],
                    [KeyboardButton(text="⬅️ Назад")],
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

@dp.message(StateFilter(AdStates.my_ad_edit_value))
async def my_ad_edit_value(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        edit_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏷️ Заголовок"), KeyboardButton(text="📝 Описание")],
                [KeyboardButton(text="📞 Контакт")],
                [KeyboardButton(text="⬅️ Назад")],
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

    try:
        database.update_ad_field(ad_id, field_name, new_value)
        ads_submenu = create_ads_submenu()
        await message.answer(f"✅ Поле успешно обновлено!", reply_markup=ads_submenu)
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при обновлении поля: {e}")
        ads_submenu = create_ads_submenu()
        await message.answer("❌ Произошла ошибка при обновлении. Попробуйте позже.", reply_markup=ads_submenu)
        await state.clear()

# --- Раздел "Потеряшки" ---
@dp.message(F.text == "➕ Сообщить")
async def finds_start_add(message: Message, state: FSMContext):
    find_type_kb = create_find_type_kb()
    await state.set_state(FindStates.choosing_type)
    await message.answer("Выберите тип записи:", reply_markup=find_type_kb)

@dp.message(StateFilter(FindStates.choosing_type))
async def finds_process_type(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        finds_submenu = create_finds_submenu()
        await state.clear()
        user_id = message.from_user.id
        if user_id in user_photos_finds:
             del user_photos_finds[user_id]
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

@dp.message(StateFilter(FindStates.entering_contact))
async def finds_process_contact(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_date = data.get('date', '')
        await message.answer(f"Когда это было? (например, 'Сегодня утром', 'Вчера вечером')\n(Текущее: {current_date})", reply_markup=cancel_kb)
        await state.set_state(FindStates.entering_date)
        return
    await state.update_data(contact=message.text)
    user_id = message.from_user.id
    user_photos_finds[user_id] = []
    await state.set_state(FindStates.uploading_photos)
    await message.answer("Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — нажмите 'Готово'.", reply_markup=cancel_kb)

@dp.message(StateFilter(FindStates.uploading_photos), F.photo)
async def finds_process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_photos_finds:
        user_photos_finds[user_id] = []
    if len(user_photos_finds[user_id]) < 3:
        user_photos_finds[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos_finds[user_id])}/3)")
        await asyncio.sleep(0.1) # Минимальная пауза
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message(StateFilter(FindStates.uploading_photos))
async def finds_process_photo_done(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos_finds.get(user_id, []))
        if photo_count > 0:
             await message.answer(f"Загрузите фото (до 3 шт, по одному). 👉 Когда закончите — нажмите 'Готово'.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        else:
             current_contact = data.get('contact', '')
             await message.answer(f"Контакт для связи (телефон, @username):\n(Текущий: {current_contact})", reply_markup=cancel_kb)
             await state.set_state(FindStates.entering_contact)
        return
    await finds_save_find(message, state)

async def finds_save_find(message: Message, state: FSMContext):
    """Функция для сохранения записи в Потеряшки."""
    data = await state.get_data()
    user_id = message.from_user.id
    find_type = data['find_type']
    item = data['item']
    description = data['description']
    location = data['location']
    date = data['date']
    contact = data['contact']
    photo_ids = user_photos_finds.get(user_id, [])
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
            photo_ids=photo_ids,
            created_at=created_at
        )
        finds_submenu = create_finds_submenu()
        if user_id in user_photos_finds:
             del user_photos_finds[user_id]
        await message.answer("✅ Запись успешно добавлена!", reply_markup=finds_submenu)
    except Exception as e:
        logging.error(f"Ошибка при добавлении записи в Потеряшки: {e}")
        finds_submenu = create_finds_submenu()
        await message.answer("❌ Произошла ошибка при добавлении записи. Попробуйте позже.", reply_markup=finds_submenu)

    await state.clear()

@dp.message(F.text == "👀 Найдено")
async def finds_show_found(message: Message):
     try:
         found_items = database.get_finds_by_type("found")
         finds_submenu = create_finds_submenu()
         if not found_items:
             await message.answer("📭 Пока никто ничего не нашел.", reply_markup=finds_submenu)
             return

         await message.answer("🔍 Найдено:", reply_markup=types.ReplyKeyboardRemove())

         for i, item in enumerate(found_items[:10]):
              text = f"""
📌 Предмет: {item[3]}
📝 Описание: {item[4]}
📍 Где: {item[5]}
📅 Когда: {item[6]}
📞 Контакт: {item[7]}
🕒 Дата публикации: {item[9]}
              """
              try:
                  await message.answer(text)
              except aiogram.exceptions.TelegramRetryAfter as e:
                  logging.warning(f"Флуд-контроль при отправке текста записи (Найдено): {e}")
                  await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                  await asyncio.sleep(e.retry_after)
                  await message.answer(text)
              except Exception as e:
                  logging.error(f"Другая ошибка при отправке текста записи (Найдено): {e}")
                  await message.answer("❌ Ошибка при отправке записи.")

              photo_ids = item[8]
              if photo_ids:
                  try:
                      photo_list = photo_ids.split(',')
                      media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                      await bot.send_media_group(chat_id=message.chat.id, media=media)
                      await asyncio.sleep(1) # Пауза после фото
                  except aiogram.exceptions.TelegramRetryAfter as e:
                      logging.warning(f"Флуд-контроль при отправке фото (Найдено): {e}")
                      await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                      await asyncio.sleep(e.retry_after)
                      try:
                          await bot.send_media_group(chat_id=message.chat.id, media=media)
                          await asyncio.sleep(1)
                      except Exception as e2:
                          logging.error(f"Ошибка при повторной отправке фото (Найдено): {e2}")
                  except Exception as e:
                      logging.error(f"Ошибка при отправке фото для записи {item[0]} (Найдено): {e}")

              # Пауза между записями
              if i < len(found_items[:10]) - 1:
                  await asyncio.sleep(1)

         await message.answer("Поиск завершен.", reply_markup=finds_submenu)
     except Exception as e:
         logging.error(f"Ошибка при показе найденных предметов: {e}")
         finds_submenu = create_finds_submenu()
         await message.answer("❌ Произошла ошибка при получении списка находок.", reply_markup=finds_submenu)

@dp.message(F.text == "🆘 Потеряно")
async def finds_show_lost(message: Message):
     try:
         lost_items = database.get_finds_by_type("lost")
         finds_submenu = create_finds_submenu()
         if not lost_items:
             await message.answer("📭 Пока никто ничего не потерял.", reply_markup=finds_submenu)
             return

         await message.answer("🆘 Потеряно:", reply_markup=types.ReplyKeyboardRemove())

         for i, item in enumerate(lost_items[:10]):
              text = f"""
📌 Предмет: {item[3]}
📝 Описание: {item[4]}
📍 Где: {item[5]}
📅 Когда: {item[6]}
📞 Контакт: {item[7]}
🕒 Дата публикации: {item[9]}
              """
              try:
                  await message.answer(text)
              except aiogram.exceptions.TelegramRetryAfter as e:
                  logging.warning(f"Флуд-контроль при отправке текста записи (Потеряно): {e}")
                  await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                  await asyncio.sleep(e.retry_after)
                  await message.answer(text)
              except Exception as e:
                  logging.error(f"Другая ошибка при отправке текста записи (Потеряно): {e}")
                  await message.answer("❌ Ошибка при отправке записи.")

              photo_ids = item[8]
              if photo_ids:
                  try:
                      photo_list = photo_ids.split(',')
                      media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                      await bot.send_media_group(chat_id=message.chat.id, media=media)
                      await asyncio.sleep(1) # Пауза после фото
                  except aiogram.exceptions.TelegramRetryAfter as e:
                      logging.warning(f"Флуд-контроль при отправке фото (Потеряно): {e}")
                      await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                      await asyncio.sleep(e.retry_after)
                      try:
                          await bot.send_media_group(chat_id=message.chat.id, media=media)
                          await asyncio.sleep(1)
                      except Exception as e2:
                          logging.error(f"Ошибка при повторной отправке фото (Потеряно): {e2}")
                  except Exception as e:
                      logging.error(f"Ошибка при отправке фото для записи {item[0]} (Потеряно): {e}")

              # Пауза между записями
              if i < len(lost_items[:10]) - 1:
                  await asyncio.sleep(1)

         await message.answer("Поиск завершен.", reply_markup=finds_submenu)
     except Exception as e:
         logging.error(f"Ошибка при показе потерянных предметов: {e}")
         finds_submenu = create_finds_submenu()
         await message.answer("❌ Произошла ошибка при получении списка потерь.", reply_markup=finds_submenu)

# --- Админка (оставлена как в предыдущем коде) ---
@dp.message(Command("admin"))
async def admin_start(message: Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return

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

    for ad in ads[:10]:
        text = f"""
🆔 ID: {ad[0]}
📌 {ad[3]}
{ad[4][:100]}...

📅 {ad[7]}
/delete_{ad[0]} - Удалить
        """
        await message.answer(text)

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
```
