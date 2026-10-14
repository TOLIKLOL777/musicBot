import logging
import os
import sqlite3
from contextlib import closing

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)
app = Celery(
    "musicBot",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
)
app.conf.update(
    enable_utc=True,
    timezone=os.getenv("CELERY_TIMEZONE", "Europe/Moscow"),
    beat_schedule={
        "clear-orders-every-monday": {
            "task": "celery_app.clear_orders",
            "schedule": crontab(minute=0, hour=0, day_of_week="mon"),
        }
    },
)


@app.task
def clear_orders() -> int:
    db_path = os.getenv("DB_PATH", "bot.db")
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute("DELETE FROM orders")
            deleted_count = cursor.rowcount

    logger.info("Еженедельная очистка заказов завершена: удалено %s", deleted_count)
    return deleted_count
