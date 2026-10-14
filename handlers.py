import re
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

import keyboards
from config import config
from db import Database

MENU_TEXT = "🎵 <b>Поиск музыкальных заказов</b>\n\nВыберите раздел:"
ADD_PROMPT = (
    "Отправьте ключевые слова — по одному на строке или через запятую.\n\n"
    "Поиск идёт по части слова без учёта регистра: «свадьб» найдёт "
    "«свадьба», «свадьбу» и «на свадьбе»."
)
ORDERS_PER_PAGE = 2
ORDER_TEXT_LIMIT = 1300

router = Router()
router.message.filter(F.from_user.id == config.owner_id)
router.callback_query.filter(F.from_user.id == config.owner_id)


class AddKeywords(StatesGroup):
    waiting = State()


class AddAllowedChat(StatesGroup):
    waiting = State()


async def send_screen(
    callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def menu_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    order_count, keyword_count, chat_count, notifications_enabled = await db.dashboard_stats()
    notification_status = "🟢 Включены" if notifications_enabled else "🔴 Выключены"
    chat_status = f"{chat_count} разрешённых" if chat_count else "Все чаты"
    text = (
        f"{MENU_TEXT}\n\n"
        f"{notification_status} уведомления · {chat_status}\n"
        f"📦 Найдено заказов: <b>{order_count}</b>"
    )
    return text, keyboards.main_menu(order_count, keyword_count)


async def update_screen_from_input(
    message: Message,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    data = await state.get_data()
    screen_message_id = data.get("screen_message_id")
    if not isinstance(screen_message_id, int):
        raise RuntimeError("Не найдено сообщение экрана для обновления.")

    await message.bot.edit_message_text(
        text,
        chat_id=message.chat.id,
        message_id=screen_message_id,
        reply_markup=markup,
    )
    await state.clear()


async def keywords_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    keywords = await db.keywords()
    hint = "Нажмите на слово, чтобы удалить его." if keywords else "Список пока пуст."
    return (
        f"🔑 <b>Ключевые слова · {len(keywords)}</b>\n\n{hint}",
        keyboards.keywords_menu(keywords),
    )


async def settings_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    enabled = await db.notifications_enabled()
    status = "✅ включены" if enabled else "⏸ выключены"
    return f"⚙️ <b>Настройки</b>\n\nУведомления: {status}", keyboards.settings_menu(enabled)


async def allowed_chats_screen(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    chats = await db.allowed_chats()
    if chats:
        hint = "Нажмите на чат, чтобы удалить его."
    else:
        hint = "Список пуст — уведомления будут приходить из всех чатов."
    return (
        f"📨 <b>Разрешённые чаты · {len(chats)}</b>\n\n{hint}",
        keyboards.allowed_chats_menu(chats),
    )


async def orders_screen(db: Database, page: int) -> tuple[str, InlineKeyboardMarkup]:
    page = max(0, page)
    orders, total = await db.orders(ORDERS_PER_PAGE, page * ORDERS_PER_PAGE)
    total_pages = (total + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
    if total_pages and page >= total_pages:
        page = total_pages - 1
        orders, _ = await db.orders(ORDERS_PER_PAGE, page * ORDERS_PER_PAGE)
    if not orders:
        return (
            "📋 <b>Заказы</b>\n\nПока нет сохранённых заказов.",
            keyboards.orders_menu([], 0, 0),
        )

    blocks = []
    for order_id, chat_title, author, text, link, status, created_at in orders:
        shown_text = text[:ORDER_TEXT_LIMIT]
        if len(text) > ORDER_TEXT_LIMIT:
            shown_text += "…"
        status_label = " 🚫 <i>Неинтересно</i>" if status == "skipped" else ""
        blocks.append(
            f"🎵 <b>Заказ #{order_id}</b>{status_label}\n"
            f"<b>Чат:</b> {escape(chat_title)}\n"
            f"<b>Кто отправил:</b> {escape(author)}\n"
            f"<b>Когда:</b> {escape(created_at)}\n"
            f"<b>Сообщение:</b>\n{escape(shown_text)}"
        )
        if link:
            blocks[-1] += f'\n<a href="{escape(link, quote=True)}">🔗 Открыть сообщение</a>'

    text = f"📋 <b>Заказы</b> · страница {page + 1}/{total_pages}\n\n"
    text += "\n\n".join(blocks)
    order_buttons = [(order[0], order[4]) for order in orders]
    return text, keyboards.orders_menu(order_buttons, page, total_pages)


CHAT_ID_HELP_TEXT = (
    "ℹ️ <b>Как найти ID группы или канала</b>\n\n"
    "1. Откройте <b>Telegram Desktop</b> (в мобильном приложении этого пункта может не быть).\n"
    "2. Перейдите в <b>Настройки → Продвинутые настройки → Экспериментальные настройки</b>.\n"
    "3. Включите показ ID (обычно называется <b>Show Peer IDs in Profile</b> / "
    "<b>Показывать ID чатов в профиле</b>).\n"
    "4. Откройте нужную группу или канал и нажмите на его название, чтобы открыть профиль. "
    "Скопируйте показанный ID.\n"
    "5. Вернитесь сюда, нажмите «Добавить чат» и отправьте ID числом.\n\n"
    "Для группы ID обычно отрицательный, например <code>-123456789</code>. "
    "Для канала или супергруппы он обычно начинается с <code>-100</code>, "
    "например <code>-1001234567890</code>. Если Telegram показывает ID без префикса "
    "<code>-100</code>, добавьте его перед числом.\n\n"
    "Важно: аккаунт, авторизованный в Telethon при первом запуске бота, должен состоять "
    "в этом чате и иметь доступ к сообщениям."
)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    text, markup = await menu_screen(db)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "menu")
async def open_menu(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await send_screen(callback, *await menu_screen(db))


@router.callback_query(F.data.startswith("orders:"))
async def open_orders(callback: CallbackQuery, db: Database) -> None:
    page_text = callback.data.split(":", 1)[1]
    if page_text == "noop":
        await callback.answer()
        return

    page = max(0, int(page_text))
    text, markup = await orders_screen(db, page)
    await send_screen(callback, text, markup)


@router.callback_query(F.data.startswith("order_del:"))
async def delete_order(callback: CallbackQuery, db: Database) -> None:
    _, order_id, page = callback.data.split(":")
    await db.delete_order(int(order_id))
    text, markup = await orders_screen(db, int(page))
    await send_screen(callback, text, markup)


@router.callback_query(F.data == "keywords")
async def open_keywords(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await send_screen(callback, *await keywords_screen(db))


@router.callback_query(F.data.startswith("kw_del:"))
async def delete_keyword(callback: CallbackQuery, db: Database) -> None:
    await db.delete_keyword(int(callback.data.split(":", 1)[1]))
    await send_screen(callback, *await keywords_screen(db))


@router.callback_query(F.data == "kw_add")
async def ask_keywords(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddKeywords.waiting)
    await state.update_data(screen_message_id=callback.message.message_id)
    await send_screen(callback, ADD_PROMPT, keyboards.cancel_menu())


@router.message(AddKeywords.waiting, F.text)
async def add_keywords(message: Message, state: FSMContext, db: Database) -> None:
    words = {word.strip().lower() for word in re.split(r"[,\n]", message.text)}
    await db.add_keywords(sorted(words - {""}))
    text, markup = await keywords_screen(db)
    await update_screen_from_input(message, state, text, markup)


@router.callback_query(F.data == "settings")
async def open_settings(callback: CallbackQuery, db: Database) -> None:
    await send_screen(callback, *await settings_screen(db))


@router.callback_query(F.data == "allowed_chats")
async def open_allowed_chats(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await send_screen(callback, *await allowed_chats_screen(db))


@router.callback_query(F.data == "chat_id_help")
async def show_chat_id_help(callback: CallbackQuery) -> None:
    await send_screen(
        callback,
        CHAT_ID_HELP_TEXT,
        keyboards.cancel_menu("allowed_chats"),
    )


@router.callback_query(F.data.startswith("chat_del:"))
async def delete_allowed_chat(callback: CallbackQuery, db: Database) -> None:
    await db.delete_allowed_chat(int(callback.data.split(":", 1)[1]))
    await send_screen(callback, *await allowed_chats_screen(db))


@router.callback_query(F.data == "chat_add")
async def ask_allowed_chat(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAllowedChat.waiting)
    await state.update_data(screen_message_id=callback.message.message_id)
    await send_screen(
        callback,
        "📨 Отправьте числовой ID группы или канала.\n\n"
        "ID группы обычно выглядит как -123456789 (скопированный ID с минусом), ID канала или супергруппы / публичные группы — "
        "как -1001234567890 (-100 + Основной скопированный ID). Положительный ID и @username не подходят.\n\n"
        "Если ID группы не подходит, то добавте -100 перед числом, например, если Telegram показывает ID 123456789, отправьте -100123456789.\n\n",
        keyboards.cancel_menu("allowed_chats"),
    )


@router.message(AddAllowedChat.waiting, F.text)
async def add_allowed_chat(
    message: Message, state: FSMContext, db: Database, client: TelegramClient
) -> None:
    raw = message.text.strip()
    try:
        chat_id = int(raw)
    except ValueError:
        await message.answer("❌ Отправьте числовой отрицательный ID группы или канала.")
        return

    if not -(1 << 63) <= chat_id < 0:
        await message.answer(
            "❌ ID группы и канала должен быть отрицательным. "
            "Для канала или супергруппы обычно используется формат -100…"
        )
        return

    matched_chat: Chat | Channel | None = None
    async for dialog in client.iter_dialogs():
        if dialog.id == chat_id and isinstance(dialog.entity, (Chat, Channel)):
            matched_chat = dialog.entity
            break

    if matched_chat is None:
        await message.answer(
            "❌ Чат с таким ID не найден среди групп и каналов аккаунта Telethon. "
            "Проверьте ID и убедитесь, что этот аккаунт состоит в чате."
        )
        return

    await db.add_allowed_chat(
        chat_id, matched_chat.title, getattr(matched_chat, "username", None)
    )
    text, markup = await allowed_chats_screen(db)
    await update_screen_from_input(message, state, text, markup)


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery, db: Database) -> None:
    await db.toggle_notifications()
    await send_screen(callback, *await settings_screen(db))


@router.callback_query(F.data.startswith("skip:"))
async def skip_order(callback: CallbackQuery, db: Database) -> None:
    link = await db.skip_order(int(callback.data.split(":", 1)[1]))
    await callback.answer()
    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n🚫 <i>Отмечено как неинтересное</i>",
        reply_markup=keyboards.link_keyboard(link) if link else None,
    )