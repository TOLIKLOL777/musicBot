import re
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import keyboards
from config import config
from db import Database

MENU_TEXT = "🎵 <b>Поиск музыкальных заказов</b>\n\nВыберите раздел:"
ADD_PROMPT = (
    "Отправьте ключевые слова — по одному на строке или через запятую.\n\n"
    "Поиск идёт по части слова без учёта регистра: «свадьб» найдёт "
    "«свадьба», «свадьбу» и «на свадьбе»."
)

router = Router()
router.message.filter(F.from_user.id == config.owner_id)
router.callback_query.filter(F.from_user.id == config.owner_id)


class AddKeywords(StatesGroup):
    waiting = State()


async def edit_screen(
    callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def keywords_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    keywords = await db.keywords()
    hint = "Нажмите на слово, чтобы удалить его." if keywords else "Список пока пуст."
    return f"🔑 <b>Ключевые слова</b>\n\n{hint}", keyboards.keywords_menu(keywords)


async def settings_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    enabled = await db.notifications_enabled()
    status = "✅ включены" if enabled else "⏸ выключены"
    return f"⚙️ <b>Настройки</b>\n\nУведомления: {status}", keyboards.settings_menu(enabled)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(MENU_TEXT, reply_markup=keyboards.main_menu())


@router.callback_query(F.data == "menu")
async def open_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_screen(callback, MENU_TEXT, keyboards.main_menu())


@router.callback_query(F.data == "keywords")
async def open_keywords(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await edit_screen(callback, *await keywords_screen(db))


@router.callback_query(F.data.startswith("kw_del:"))
async def delete_keyword(callback: CallbackQuery, db: Database) -> None:
    await db.delete_keyword(int(callback.data.split(":", 1)[1]))
    await edit_screen(callback, *await keywords_screen(db))


@router.callback_query(F.data == "kw_add")
async def ask_keywords(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddKeywords.waiting)
    await edit_screen(callback, ADD_PROMPT, keyboards.cancel_menu())


@router.message(AddKeywords.waiting, F.text)
async def add_keywords(message: Message, state: FSMContext, db: Database) -> None:
    words = {word.strip().lower() for word in re.split(r"[,\n]", message.text)}
    for word in words - {""}:
        await db.add_keyword(word)
    await state.clear()
    text, markup = await keywords_screen(db)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "settings")
async def open_settings(callback: CallbackQuery, db: Database) -> None:
    await edit_screen(callback, *await settings_screen(db))


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery, db: Database) -> None:
    await db.toggle_notifications()
    await edit_screen(callback, *await settings_screen(db))


@router.callback_query(F.data.startswith("skip:"))
async def skip_order(callback: CallbackQuery, db: Database) -> None:
    link = await db.skip_order(int(callback.data.split(":", 1)[1]))
    await edit_screen(
        callback,
        f"{callback.message.html_text}\n\n🚫 <i>Отмечено как неинтересное</i>",
        keyboards.link_keyboard(link) if link else None,
    )