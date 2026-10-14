from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Все заказы", callback_data="orders:0")],
            [InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="keywords")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        ]
    )


def keywords_menu(keywords: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for keyword_id, word in keywords:
        builder.button(text=f"❌ {word}", callback_data=f"kw_del:{keyword_id}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="➕ Добавить", callback_data="kw_add"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu"))
    return builder.as_markup()


def cancel_menu(target: str = "keywords") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data=target)]]
    )


def settings_menu(notifications_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Выключить уведомления" if notifications_enabled else "▶️ Включить уведомления"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="toggle_notifications")],
            [InlineKeyboardButton(text="📨 Разрешённые чаты", callback_data="allowed_chats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ]
    )


def allowed_chats_menu(chats: list[tuple[int, int, str | None, str | None]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for _, chat_id, title, username in chats:
        label = title or (f"@{username}" if username else f"ID {chat_id}")
        builder.button(text=f"❌ {label}", callback_data=f"chat_del:{chat_id}")

    if chats:
        builder.adjust(1)
    builder.row(InlineKeyboardButton(text="➕ Добавить чат", callback_data="chat_add"))
    builder.row(InlineKeyboardButton(text="ℹ️ Где найти ID чата?", callback_data="chat_id_help"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="settings"))
    return builder.as_markup()


def orders_menu(
    orders: list[tuple[int, str | None]],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order_id, link in orders:
        row = [
            InlineKeyboardButton(
                text=f"🗑 Удалить заказ #{order_id}",
                callback_data=f"order_del:{order_id}:{page}",
            )
        ]
        if link:
            row.insert(0, InlineKeyboardButton(text="🔗 Открыть", url=link))
        builder.row(*row)

    if total_pages > 1:
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"orders:{page - 1}")
            )
        navigation.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="orders:noop")
        )
        if page + 1 < total_pages:
            navigation.append(
                InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"orders:{page + 1}")
            )
        builder.row(*navigation)

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu"))
    return builder.as_markup()


def link_keyboard(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Открыть сообщение", url=link)]]
    )


def order_keyboard(order_id: int, link: str | None) -> InlineKeyboardMarkup:
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="🔗 Открыть сообщение", url=link)])
    rows.append([InlineKeyboardButton(text="🚫 Неинтересно", callback_data=f"skip:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)