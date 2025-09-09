# bot.py
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta
import asyncio
import logging
import aiogram.exceptions  # Для обработки TelegramRetryAfter

import config
import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
database.init_db()

# Храним фото временно
user_photos = {}

# --- Константы ---
CATEGORIES_LIST = [
    "🏠 Недвижимость", "🚗 Транспорт",
    "💼 Работа/Услуги", "🛒 Вещи",
    "🐶 Отдам даром", "🎓 Обучение"
]

# --- Клавиатуры ---
def create_main_menu():
    """Создает главное меню в 2 столбца."""
    # Получаем общее количество объявлений для кнопки "Все объявления"
    try:
        total_ads_count = len(database.get_all_ads())
    except Exception as e:
        logging.error(f"Ошибка при получении общего количества объявлений: {e}")
        total_ads_count = 0

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Подать объявление"), KeyboardButton(text=f"🔍 Все объявления ({total_ads_count})")],
            [KeyboardButton(text="📂 По категориям"), KeyboardButton(text="👤 Мои объявления")],
        ],
        resize_keyboard=True
    )

def create_categories_keyboard():
    """Клавиатура категорий для подачи объявления (2 колонки)."""
    kb_rows = []
    for i in range(0, len(CATEGORIES_LIST), 2):
        row = [KeyboardButton(text=cat) for cat in CATEGORIES_LIST[i:i+2]]
        kb_rows.append(row)
    kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=kb_rows, resize_keyboard=True)

def create_browse_categories_keyboard():
    """Клавиатура категорий для просмотра (2 колонки с количеством)."""
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
    kb_rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=kb_rows, resize_keyboard=True)

# Клавиатура "Отмена/Назад"
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
    resize_keyboard=True
)

# --- Состояния ---
class AdStates(StatesGroup):
    category = State()
    title = State()
    description = State()
    photo = State()
    contact = State()
    browse_category = State()
    my_ads_list = State()
    my_ad_selected = State()
    my_ad_edit_field = State()
    my_ad_edit_value = State()
    # --- Состояния для комментариев ---
    viewing_ad = State()
    viewing_comments = State()
    entering_comment = State()

# --- Инициализация бота ---
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: Message):
    """Обработчик команды /start. Добавляет пользователя в БД."""
    # Добавляем пользователя в БД при первом взаимодействии
    user_id = message.from_user.id
    username = message.from_user.username
    database.add_user(user_id, username)

    logging.info(f"Пользователь {user_id} запустил бота.")
    # Небольшая пауза перед отправкой, чтобы избежать флуда при быстром переподключении
    await asyncio.sleep(0.1)
    main_menu = create_main_menu()
    try:
        await message.answer(
            "📢 Добро пожаловать в Объявления!\nВыберите действие:",
            reply_markup=main_menu
        )
        logging.info(f"Приветственное сообщение отправлено пользователю {user_id}.")
    except aiogram.exceptions.TelegramRetryAfter as e:
        logging.warning(f"Флуд-контроль при отправке приветствия пользователю {user_id}: {e}")
        # В данном случае мы ничего не отправляем, пусть пользователь сам нажмет /start еще раз
    except Exception as e:
        logging.error(f"Ошибка при отправке приветствия пользователю {user_id}: {e}")

# --- Подача объявления ---
@dp.message(F.text == "➕ Подать объявление")
async def new_ad_start(message: Message, state: FSMContext):
    categories_kb = create_categories_keyboard()
    await message.answer("Выберите категорию:", reply_markup=categories_kb)
    await state.set_state(AdStates.category)

@dp.message(StateFilter(AdStates.category))
async def process_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        main_menu = create_main_menu()
        await state.clear()
        user_id = message.from_user.id
        if user_id in user_photos:
            del user_photos[user_id]
        await message.answer("Главное меню", reply_markup=main_menu)
        return

    if message.text not in CATEGORIES_LIST:
        categories_kb = create_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка.", reply_markup=categories_kb)
        return

    await state.update_data(category=message.text)
    await message.answer("Введите заголовок объявления:", reply_markup=cancel_kb)
    await state.set_state(AdStates.title)

@dp.message(StateFilter(AdStates.title))
async def process_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await new_ad_start(message, state)
        return
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления:", reply_markup=cancel_kb)
    await state.set_state(AdStates.description)

@dp.message(StateFilter(AdStates.description))
async def process_description(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        current_title = data.get('title', '')
        await message.answer(f"Введите заголовок объявления:\n(Текущий: {current_title})", reply_markup=cancel_kb)
        await state.set_state(AdStates.title)
        return
    await state.update_data(description=message.text)
    user_id = message.from_user.id
    user_photos[user_id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). Когда закончите — отправьте любой текст.", reply_markup=cancel_kb)
    await state.set_state(AdStates.photo)

@dp.message(StateFilter(AdStates.photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_photos:
        user_photos[user_id] = []
    if len(user_photos[user_id]) < 3:
        user_photos[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos[user_id])}/3)")
        await asyncio.sleep(0.1)
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message(StateFilter(AdStates.photo))
async def process_photo_done(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos.get(user_id, []))
        if photo_count > 0:
            await message.answer(f"Загрузите фото (до 3 шт, по одному). Когда закончите — отправьте любой текст.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
        else:
            current_desc = data.get('description', '')
            await message.answer(f"Введите описание объявления:\n(Текущее: {current_desc[:50]}...)", reply_markup=cancel_kb)
            await state.set_state(AdStates.description)
        return
    await message.answer("Введите контакт (телефон, @username):", reply_markup=cancel_kb)
    await state.set_state(AdStates.contact)

@dp.message(StateFilter(AdStates.contact))
async def process_contact(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        user_id = message.from_user.id
        photo_count = len(user_photos.get(user_id, []))
        await message.answer(f"Загрузите фото (до 3 шт, по одному). Когда закончите — отправьте любой текст.\n(Загружено: {photo_count})", reply_markup=cancel_kb)
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
        main_menu = create_main_menu()
        if user_id in user_photos:
            del user_photos[user_id]
        await message.answer("✅ Объявление успешно опубликовано!", reply_markup=main_menu)

        # --- Уведомление админу о новом объявлении ---
        try:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"🔔 Новое объявление!\nКатегория: {data['category']}\nЗаголовок: {data['title']}\nАвтор: {user_id}"
            )
            logging.info("Уведомление о новом объявлении отправлено админу.")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления админу: {e}")

    except Exception as e:
        logging.error(f"Ошибка при добавлении объявления: {e}")
        main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при публикации. Попробуйте позже.", reply_markup=main_menu)

    await state.clear()

# --- Просмотр всех объявлений ---
@dp.message(lambda message: message.text and message.text.startswith("🔍 Все объявления"))
async def show_all_ads(message: Message, state: FSMContext):
    try:
        ads = database.get_all_ads()
    except Exception as e:
        logging.error(f"Ошибка в show_all_ads (получение из БД): {e}")
        main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при получении объявлений.", reply_markup=main_menu)
        return

    if not ads:
        main_menu = create_main_menu()
        await message.answer("📭 Пока нет объявлений.", reply_markup=main_menu)
        return

    main_menu = create_main_menu()
    await message.answer("📄 Все объявления:", reply_markup=types.ReplyKeyboardRemove())

    for i, ad in enumerate(ads[:5]):
        text = f"""
📌 {ad[3]}
💬 {ad[4][:100]}...

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
        """
        try:
            await message.answer(text)
        except aiogram.exceptions.TelegramRetryAfter as e:
            logging.warning(f"Флуд-контроль при отправке текста объявления: {e}")
            await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
            await asyncio.sleep(e.retry_after)
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
                await asyncio.sleep(1) # Пауза после фото
            except aiogram.exceptions.TelegramRetryAfter as e:
                logging.warning(f"Флуд-контроль при отправке фото: {e}")
                await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                await asyncio.sleep(e.retry_after)
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

    await message.answer("Просмотр завершен.", reply_markup=main_menu)
    await state.clear()

# --- Просмотр по категориям ---
@dp.message(F.text == "📂 По категориям")
async def browse_categories_start(message: Message, state: FSMContext):
    browse_kb = create_browse_categories_keyboard()
    await message.answer("Выберите категорию для просмотра:", reply_markup=browse_kb)
    await state.set_state(AdStates.browse_category)

@dp.message(StateFilter(AdStates.browse_category))
async def process_browse_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        main_menu = create_main_menu()
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
        return

    # Извлекаем название категории без количества "(...)"
    selected_category_text = message.text.split(" (")[0]
    if selected_category_text not in CATEGORIES_LIST:
        browse_kb = create_browse_categories_keyboard()
        await message.answer("Пожалуйста, выберите категорию из списка.", reply_markup=browse_kb)
        return

    category = selected_category_text
    try:
        ads = database.get_ads_by_category(category)
    except Exception as e:
        logging.error(f"Ошибка в process_browse_category: {e}")
        main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при поиске объявлений. Попробуйте позже.", reply_markup=main_menu)
        await state.clear()
        return

    if not ads:
        main_menu = create_main_menu()
        await message.answer(f"📭 Пока нет объявлений в категории '{category}'.", reply_markup=main_menu)
        await state.clear()
        return

    main_menu = create_main_menu()
    await message.answer(f"📄 Объявления в категории '{category}':", reply_markup=types.ReplyKeyboardRemove())

    for i, ad in enumerate(ads[:5]):
        text = f"""
📌 {ad[3]}
💬 {ad[4][:100]}...

📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
        """
        try:
            await message.answer(text)
        except aiogram.exceptions.TelegramRetryAfter as e:
            logging.warning(f"Флуд-контроль при отправке текста объявления (поиск): {e}")
            await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
            await asyncio.sleep(e.retry_after)
            await message.answer(text)
        except Exception as e:
            logging.error(f"Другая ошибка при отправке текста объявления (поиск): {e}")
            await message.answer("❌ Ошибка при отправке объявления.")

        photo_ids = ad[5]
        if photo_ids:
            try:
                photo_list = photo_ids.split(',')
                media = [types.InputMediaPhoto(media=pid) for pid in photo_list[:10]]
                await bot.send_media_group(chat_id=message.chat.id, media=media)
                await asyncio.sleep(1) # Пауза после фото
            except aiogram.exceptions.TelegramRetryAfter as e:
                logging.warning(f"Флуд-контроль при отправке фото (поиск): {e}")
                await message.answer(f"⏳ Пожалуйста, подождите {e.retry_after} секунд...")
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_media_group(chat_id=message.chat.id, media=media)
                    await asyncio.sleep(1)
                except Exception as e2:
                    logging.error(f"Ошибка при повторной отправке фото (поиск): {e2}")
            except Exception as e:
                logging.error(f"Ошибка при отправке фото для объявления {ad[0]} (поиск): {e}")

        # Пауза между объявлениями
        if i < len(ads[:5]) - 1:
            await asyncio.sleep(1)

    await message.answer("Поиск завершен.", reply_markup=main_menu)
    await state.clear()

# --- Мои объявления ---
@dp.message(F.text == "👤 Мои объявления")
async def my_ads_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        user_ads = database.get_ads_by_user_id(user_id)
    except Exception as e:
        logging.error(f"Ошибка в my_ads_start (получение из БД): {e}")
        main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при получении ваших объявлений.", reply_markup=main_menu)
        return

    if not user_ads:
        main_menu = create_main_menu()
        await message.answer("📭 У вас пока нет объявлений.", reply_markup=main_menu)
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
        main_menu = create_main_menu()
        await state.clear()
        await message.answer("Главное меню", reply_markup=main_menu)
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

        # Сохраняем ID объявления в состоянии для дальнейшего использования
        await state.update_data(current_ad_id=selected_ad[0])

        # Формируем текст объявления
        ad_text = f"""
🆔 ID: {selected_ad[0]}
📌 Категория: {selected_ad[2]}
🏷️ Заголовок: {selected_ad[3]}
📝 Описание: {selected_ad[4]}
📞 Контакт: {selected_ad[6]}
📅 Дата: {selected_ad[7]}
        """
        await message.answer(ad_text)

        # Создаем клавиатуру с действиями для объявления
        ad_actions_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💬 Комментарии"), KeyboardButton(text="✏️ Редактировать")],
                [KeyboardButton(text="🗑️ Удалить"), KeyboardButton(text="⬅️ Назад")],
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите действие:", reply_markup=ad_actions_kb)
        # Устанавливаем состояние просмотра объявления
        await state.set_state(AdStates.viewing_ad)

    except (ValueError, IndexError, StopIteration) as e:
        logging.error(f"Ошибка в my_ads_select: {e}")
        await message.answer("❌ Неверный формат. Пожалуйста, выберите объявление из списка.")

# --- Просмотр комментариев к объявлению ---
@dp.message(StateFilter(AdStates.viewing_ad), F.text == "💬 Комментарии")
async def view_comments(message: Message, state: FSMContext):
    """Показывает комментарии к текущему объявлению."""
    data = await state.get_data()
    ad_id = data.get('current_ad_id')

    if not ad_id:
        await message.answer("❌ Ошибка. Не удалось определить объявление.")
        # Возвращаем в главное меню или к выбору объявления
        main_menu = create_main_menu()
        await message.answer("Возврат в главное меню.", reply_markup=main_menu)
        await state.clear()
        return

    try:
        comments = database.get_comments_by_ad_id(ad_id)
    except Exception as e:
        logging.error(f"Ошибка при получении комментариев для объявления {ad_id}: {e}")
        await message.answer("❌ Произошла ошибка при получении комментариев.")
        return

    if not comments:
        await message.answer("📭 Пока нет комментариев. Будьте первым!")
    else:
        await message.answer("💬 Комментарии к объявлению:")
        for comment in comments[-10:]: # Показываем последние 10
            # comment[5] - username, comment[3] - text, comment[4] - created_at
            username_display = f"@{comment[5]}" if comment[5] else f"ID:{comment[2]}"
            comment_text = f"{username_display} ({comment[4]}):\n{comment[3]}"
            await message.answer(comment_text)
            await asyncio.sleep(0.1) # Минимальная пауза

    # Клавиатура для добавления комментария или возврата
    comment_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Написать комментарий")],
            [KeyboardButton(text="⬅️ Назад к объявлению")],
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите действие:", reply_markup=comment_kb)
    # Переходим в состояние просмотра комментариев
    await state.set_state(AdStates.viewing_comments)

# --- Ввод нового комментария ---
@dp.message(StateFilter(AdStates.viewing_comments), F.text == "✍️ Написать комментарий")
async def prompt_new_comment(message: Message, state: FSMContext):
    """Предлагает пользователю ввести текст комментария."""
    await message.answer("Введите ваш комментарий (до 200 символов):", reply_markup=cancel_kb)
    await state.set_state(AdStates.entering_comment)

@dp.message(StateFilter(AdStates.entering_comment))
async def process_new_comment(message: Message, state: FSMContext):
    """Обрабатывает введенный пользователем комментарий."""
    if message.text == "⬅️ Назад":
        # Возвращаемся к просмотру комментариев
        await view_comments(message, state) # Повторно вызываем, чтобы обновить список
        return

    comment_text = message.text.strip()
    if not comment_text:
        await message.answer("Комментарий не может быть пустым. Пожалуйста, введите текст.")
        return
    if len(comment_text) > 200:
        await message.answer("Комментарий слишком длинный (максимум 200 символов). Пожалуйста, сократите.")
        return

    data = await state.get_data()
    ad_id = data.get('current_ad_id')
    user_id = message.from_user.id
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    if not ad_id:
        await message.answer("❌ Ошибка. Не удалось определить объявление.")
        main_menu = create_main_menu()
        await message.answer("Возврат в главное меню.", reply_markup=main_menu)
        await state.clear()
        return

    try:
        database.add_comment(ad_id, user_id, comment_text, created_at)
        await message.answer("✅ Комментарий добавлен!")

        # --- Уведомление автору объявления (ОПЦИОНАЛЬНО) ---
        try:
            ad = database.get_ad_by_id(ad_id)
            if ad and ad[1] != user_id: # ad[1] - user_id автора объявления
                notification_text = f"🔔 Новый комментарий к вашему объявлению #{ad_id}:\n{comment_text[:50]}..."
                await bot.send_message(chat_id=ad[1], text=notification_text)
                logging.info(f"Уведомление о комментарии отправлено автору {ad[1]}.")
        except aiogram.exceptions.TelegramForbiddenError:
            logging.info(f"Не удалось уведомить автора {ad[1]}: запрещено (бот заблокирован).")
        except Exception as e:
            logging.error(f"Ошибка при уведомлении автора {ad[1]}: {e}")
        # ---

    except Exception as e:
        logging.error(f"Ошибка при добавлении комментария к объявлению {ad_id}: {e}")
        await message.answer("❌ Произошла ошибка при добавлении комментария.")

    # Возвращаемся к просмотру комментариев (обновленному)
    await view_comments(message, state)

# --- Возврат к просмотру объявления из комментариев ---
@dp.message(StateFilter(AdStates.viewing_comments), F.text == "⬅️ Назад к объявлению")
async def back_to_ad_from_comments(message: Message, state: FSMContext):
    """Возвращает к просмотру основной информации об объявлении."""
    data = await state.get_data()
    ad_id = data.get('current_ad_id')

    if not ad_id:
        await message.answer("❌ Ошибка. Не удалось определить объявление.")
        main_menu = create_main_menu()
        await message.answer("Возврат в главное меню.", reply_markup=main_menu)
        await state.clear()
        return

    try:
        # Получаем объявление из БД
        ad = database.get_ad_by_id(ad_id)
        if not ad:
             await message.answer("❌ Объявление не найдено.")
             main_menu = create_main_menu()
             await message.answer("Возврат в главное меню.", reply_markup=main_menu)
             await state.clear()
             return

        # Показываем объявление снова
        ad_text = f"""
🆔 ID: {ad[0]}
📌 Категория: {ad[2]}
🏷️ Заголовок: {ad[3]}
📝 Описание: {ad[4]}
📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
        """
        await message.answer(ad_text)

        # Создаем клавиатуру с действиями для объявления
        ad_actions_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💬 Комментарии"), KeyboardButton(text="✏️ Редактировать")],
                [KeyboardButton(text="🗑️ Удалить"), KeyboardButton(text="⬅️ Назад")],
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите действие:", reply_markup=ad_actions_kb)
        # Возвращаемся в состояние просмотра объявления
        await state.set_state(AdStates.viewing_ad)

    except Exception as e:
        logging.error(f"Ошибка при возврате к объявлению {ad_id}: {e}")
        await message.answer("❌ Произошла ошибка.")
        main_menu = create_main_menu()
        await message.answer("Возврат в главное меню.", reply_markup=main_menu)
        await state.clear()

# --- Возврат к просмотру объявления из самого объявления ---
# (Этот обработчик нужен, если пользователь был в viewing_ad и нажал "⬅️ Назад")
@dp.message(StateFilter(AdStates.viewing_ad), F.text == "⬅️ Назад")
async def back_to_my_ads_from_ad(message: Message, state: FSMContext):
    """Возвращает к списку 'Мои объявления'."""
    await my_ads_start(message, state) # Повторно вызываем, чтобы показать список

# --- Действия с выбранным объявлением ---
@dp.message(StateFilter(AdStates.viewing_ad))
async def my_ad_action_from_view(message: Message, state: FSMContext):
    """Обрабатывает действия с объявления (редактирование, удаление) из состояния просмотра."""
    if message.text == "⬅️ Назад":
        await my_ads_start(message, state)
        return

    if message.text == "🗑️ Удалить":
        data = await state.get_data()
        ad_id = data.get('current_ad_id')
        if ad_id:
            try:
                database.delete_ad(ad_id)
                main_menu = create_main_menu()
                await message.answer(f"✅ Объявление #{ad_id} удалено!", reply_markup=main_menu)
                await state.clear()
            except Exception as e:
                logging.error(f"Ошибка при удалении объявления #{ad_id}: {e}")
                main_menu = create_main_menu()
                await message.answer("❌ Произошла ошибка при удалении.", reply_markup=main_menu)
                await state.clear()
        else:
            main_menu = create_main_menu()
            await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=main_menu)
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

# --- Выбор поля для редактирования ---
@dp.message(StateFilter(AdStates.my_ad_edit_field))
async def my_ad_edit_field(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        data = await state.get_data()
        ad_id = data.get('current_ad_id')
        if ad_id:
            try:
                ad = database.get_ad_by_id(ad_id)
                if ad:
                    ad_text = f"""
🆔 ID: {ad[0]}
📌 Категория: {ad[2]}
🏷️ Заголовок: {ad[3]}
📝 Описание: {ad[4]}
📞 Контакт: {ad[6]}
📅 Дата: {ad[7]}
                    """
                    await message.answer(ad_text)
                    ad_actions_kb = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="💬 Комментарии"), KeyboardButton(text="✏️ Редактировать")],
                            [KeyboardButton(text="🗑️ Удалить"), KeyboardButton(text="⬅️ Назад")],
                        ],
                        resize_keyboard=True
                    )
                    await message.answer("Выберите действие:", reply_markup=ad_actions_kb)
                    await state.set_state(AdStates.viewing_ad)
                else:
                    raise ValueError("Объявление не найдено")
            except Exception as e:
                logging.error(f"Ошибка при возврате к объявлению {ad_id}: {e}")
                main_menu = create_main_menu()
                await message.answer("❌ Ошибка.", reply_markup=main_menu)
                await state.clear()
        else:
            main_menu = create_main_menu()
            await message.answer("❌ Ошибка.", reply_markup=main_menu)
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
        ad_id = data.get('current_ad_id')
        if ad_id:
            try:
                ad = database.get_ad_by_id(ad_id)
                if ad:
                    current_value = ""
                    if field_name == "title":
                        current_value = ad[3]
                    elif field_name == "description":
                        current_value = ad[4]
                    elif field_name == "contact":
                        current_value = ad[6]
                    await message.answer(f"Введите новое значение для '{message.text}':\n(Текущее: {current_value})", reply_markup=cancel_kb)
                else:
                    raise ValueError("Объявление не найдено")
            except Exception as e:
                logging.error(f"Ошибка при получении объявления {ad_id} для редактирования: {e}")
                main_menu = create_main_menu()
                await message.answer("❌ Ошибка.", reply_markup=main_menu)
                await state.clear()
    else:
        await message.answer("Пожалуйста, выберите поле из списка.")

# --- Ввод нового значения ---
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
    ad_id = data.get('current_ad_id')
    field_name = data.get('editing_field')

    if not ad_id or not field_name:
        main_menu = create_main_menu()
        await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=main_menu)
        await state.clear()
        return

    try:
        database.update_ad_field(ad_id, field_name, new_value)
        main_menu = create_main_menu()
        await message.answer(f"✅ Поле успешно обновлено!", reply_markup=main_menu)
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при обновлении поля: {e}")
        main_menu = create_main_menu()
        await message.answer("❌ Произошла ошибка при обновлении. Попробуйте позже.", reply_markup=main_menu)
        await state.clear()

# --- Админка ---
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

    await message.answer("🔧 Админ-панель\nВведите /admin_list для просмотра всех объявлений\nВведите /broadcast <текст> для рассылки\nВведите /stats для статистики")

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

# --- Рассылка от администратора ---
@dp.message(Command("broadcast"))
async def broadcast_message(message: Message, command: CommandObject):
    """Отправляет сообщение всем пользователям бота. Использование: /broadcast <текст сообщения>"""
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return

    # Получаем текст сообщения после команды
    if not command.args:
        await message.answer("Пожалуйста, введите текст сообщения после команды /broadcast\nПример: /broadcast Привет всем!")
        return

    text_to_send = command.args
    await message.answer("⏳ Начинаю рассылку...")

    try:
        user_ids = database.get_all_users()
        if not user_ids:
             await message.answer("📭 Нет пользователей для рассылки.")
             return

        count = 0
        count_blocked = 0
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, text=text_to_send)
                count += 1
                # Пауза, чтобы не превысить лимиты Telegram
                # Согласно FAQ: ~30 сообщений в секунду бесплатно.
                # Пауза 1/30 = 0.033 секунды. Сделаем немного больше для надежности.
                await asyncio.sleep(0.05)
            except aiogram.exceptions.TelegramForbiddenError:
                # Пользователь заблокировал бота
                logging.info(f"Пользователь {user_id} заблокировал бота, пропускаем.")
                count_blocked += 1
            except aiogram.exceptions.TelegramRetryAfter as e:
                # Очень много сообщений, даже с паузами
                logging.warning(f"Флуд-контроль при рассылке: {e}. Ждем {e.retry_after} секунд.")
                await message.answer(f"⏳ Флуд-контроль: ждем {e.retry_after} секунд...")
                await asyncio.sleep(e.retry_after)
                # Повторная попытка отправить сообщение этому пользователю
                try:
                     await bot.send_message(chat_id=user_id, text=text_to_send)
                     count += 1
                     await asyncio.sleep(0.05)
                except Exception as e2:
                     logging.error(f"Ошибка при повторной отправке сообщения пользователю {user_id}: {e2}")
                     # Не увеличиваем счетчик, считаем как неудачную попытку
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                # Не прерываем рассылку из-за ошибки у одного пользователя

        await message.answer(f"✅ Рассылка завершена!\nСообщение отправлено: {count}\nЗаблокировали бота: {count_blocked}")
    except Exception as e:
        logging.error(f"Ошибка в /broadcast: {e}")
        await message.answer("❌ Произошла ошибка при рассылке.")

# --- Статистика для администратора ---
@dp.message(Command("stats"))
async def show_stats(message: Message):
    """Показывает базовую статистику бота."""
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return

    try:
        # --- Сбор данных ---
        total_ads = len(database.get_all_ads())
        total_users = len(database.get_all_users())

        # Количество объявлений по категориям
        category_stats = {}
        for cat in CATEGORIES_LIST:
            try:
                count = len(database.get_ads_by_category(cat))
                category_stats[cat] = count
            except Exception as e:
                logging.error(f"Ошибка при подсчете статистики для категории '{cat}': {e}")
                category_stats[cat] = 0

        # Сортировка категорий по количеству
        sorted_categories = sorted(category_stats.items(), key=lambda item: item[1], reverse=True)

        # --- Формирование сообщения ---
        stats_text = f"""
📊 <b>Статистика бота</b>

👥 <b>Пользователи:</b> {total_users}
📢 <b>Объявления:</b> {total_ads}

📂 <b>По категориям:</b>
"""
        for cat, count in sorted_categories:
            stats_text += f"• {cat}: {count}\n"

        await message.answer(stats_text, parse_mode='HTML')

    except Exception as e:
        logging.error(f"Ошибка в /stats: {e}")
        await message.answer("❌ Произошла ошибка при получении статистики.")

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
