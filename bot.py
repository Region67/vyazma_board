# bot.py
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from datetime import datetime

import config
import database
import keyboards
import states

bot = Bot(token=config.API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

database.init_db()

user_photos = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "📢 Добро пожаловать в [Город] Объявления!\nВыберите действие:",
        reply_markup=keyboards.main_menu
    )

@dp.message_handler(text="➕ Подать объявление")
async def new_ad_start(message: types.Message):
    await message.answer("Выберите категорию:", reply_markup=keyboards.categories_kb)
    await states.AdStates.category.set()

@dp.message_handler(state=states.AdStates.category)
async def process_category(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await message.answer("Главное меню", reply_markup=keyboards.main_menu)
        return
    await state.update_data(category=message.text)
    await message.answer("Введите заголовок объявления:")
    await states.AdStates.title.set()

@dp.message_handler(state=states.AdStates.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления:")
    await states.AdStates.description.set()

@dp.message_handler(state=states.AdStates.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    user_photos[message.from_user.id] = []
    await message.answer("Загрузите фото (до 3 шт, по одному). Когда закончите — нажмите 'Далее'")
    await states.AdStates.photo.set()

@dp.message_handler(content_types=['photo'], state=states.AdStates.photo)
async def process_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if len(user_photos[user_id]) < 3:
        user_photos[user_id].append(message.photo[-1].file_id)
        await message.answer(f"Фото добавлено ({len(user_photos[user_id])}/3)")
    else:
        await message.answer("Можно загрузить максимум 3 фото.")

@dp.message_handler(text="Далее", state=states.AdStates.photo)
async def process_next(message: types.Message, state: FSMContext):
    await message.answer("Введите контакт (телефон, @username или слово 'через бота'):")
    await states.AdStates.contact.set()

@dp.message_handler(state=states.AdStates.contact)
async def process_contact(message: types.Message, state: FSMContext):
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

    await message.answer("✅ Объявление успешно опубликовано!", reply_markup=keyboards.main_menu)
    await state.finish()
    if user_id in user_photos:
        del user_photos[user_id]

@dp.message_handler(text="🔍 Все объявления")
async def show_ads(message: types.Message):
    ads = database.get_all_ads()
    if not ads:
        await message.answer("Пока нет объявлений.")
        return
    for ad in ads[:5]:
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
            media = [types.InputMediaPhoto(media=pid) for pid in photo_list]
            await bot.send_media_group(chat_id=message.chat.id, media=media)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
