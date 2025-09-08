# states.py
from aiogram.dispatcher.filters.state import State, StatesGroup

class AdStates(StatesGroup):
    category = State()
    title = State()
    description = State()
    photo = State()
    contact = State()
