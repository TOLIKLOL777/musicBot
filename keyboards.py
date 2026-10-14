from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
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


def cancel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="keywords")]]
    )


def settings_menu(notifications_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Выключить уведомления" if notifications_enabled else "▶️ Включить уведомления"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="toggle_notifications")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ]
    )


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