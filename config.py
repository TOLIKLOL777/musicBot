import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int
    api_id: int
    api_hash: str
    session_name: str
    db_path: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Не задана переменная {name}. Проверьте файл .env")
    return value


def load_config() -> Config:
    load_dotenv()
    return Config(
        bot_token=_required("BOT_TOKEN"),
        owner_id=int(_required("OWNER_ID")),
        api_id=int(_required("API_ID")),
        api_hash=_required("API_HASH"),
        session_name=os.getenv("SESSION_NAME", "watcher"),
        db_path=os.getenv("DB_PATH", "bot.db"),
    )


config = load_config()