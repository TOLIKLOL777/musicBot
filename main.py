import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from telethon import TelegramClient

from config import config
from db import Database
from handlers import router
from watcher import register_watcher


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    db = await Database.connect(config.db_path)
    bot = Bot(
        config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    client = TelegramClient(config.session_name, config.api_id, config.api_hash)
    register_watcher(client, bot, db)

    dispatcher = Dispatcher(db=db, client=client)
    dispatcher.include_router(router)

    await client.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await client.disconnect()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass