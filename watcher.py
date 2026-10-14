from html import escape

from aiogram import Bot
from telethon import TelegramClient, events
from telethon.tl.types import Channel, User

import keyboards
from config import config
from db import Database

MAX_TEXT_LENGTH = 3000


def author_name(sender, chat_title: str) -> str:
    if isinstance(sender, User):
        name = " ".join(part for part in (sender.first_name, sender.last_name) if part)
        name = name or "Без имени"
        return f"{name} (@{sender.username})" if sender.username else name
    return getattr(sender, "title", chat_title)


def message_link(chat, message_id: int) -> str | None:
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    if isinstance(chat, Channel):
        return f"https://t.me/c/{chat.id}/{message_id}"
    return None


def format_notification(chat_title: str, author: str, text: str) -> str:
    shown = text if len(text) <= MAX_TEXT_LENGTH else text[:MAX_TEXT_LENGTH] + "…"
    return (
        "🎵 <b>Возможный заказ</b>\n\n"
        f"<b>Чат:</b> {escape(chat_title)}\n"
        f"<b>Автор:</b> {escape(author)}\n\n"
        f"{escape(shown)}"
    )


def register_watcher(client: TelegramClient, bot: Bot, db: Database) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def on_message(event: events.NewMessage.Event) -> None:
        if event.is_private or not event.raw_text:
            return
        if not await db.notifications_enabled():
            return

        text = event.raw_text
        lowered = text.lower()
        if not any(word in lowered for _, word in await db.keywords()):
            return

        chat = await event.get_chat()
        author = author_name(await event.get_sender(), chat.title)
        link = message_link(chat, event.message.id)

        order_id = await db.add_order(
            event.chat_id, event.message.id, chat.title, author, text, link
        )
        if order_id is None:
            return

        await bot.send_message(
            config.owner_id,
            format_notification(chat.title, author, text),
            reply_markup=keyboards.order_keyboard(order_id, link),
        )