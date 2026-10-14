import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    chat_title TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    link TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chat_id, message_id)
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('notifications', 1);
"""


class Database:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def connect(cls, path: str) -> "Database":
        conn = await aiosqlite.connect(path)
        await conn.executescript(SCHEMA)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

    async def keywords(self) -> list[tuple[int, str]]:
        async with self._conn.execute("SELECT id, word FROM keywords ORDER BY word") as cursor:
            return [(row[0], row[1]) for row in await cursor.fetchall()]

    async def add_keyword(self, word: str) -> None:
        await self._conn.execute("INSERT OR IGNORE INTO keywords (word) VALUES (?)", (word,))
        await self._conn.commit()

    async def delete_keyword(self, keyword_id: int) -> None:
        await self._conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        await self._conn.commit()

    async def notifications_enabled(self) -> bool:
        async with self._conn.execute(
            "SELECT value FROM settings WHERE key = 'notifications'"
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row[0])

    async def toggle_notifications(self) -> None:
        await self._conn.execute(
            "UPDATE settings SET value = 1 - value WHERE key = 'notifications'"
        )
        await self._conn.commit()

    async def add_order(
        self,
        chat_id: int,
        message_id: int,
        chat_title: str,
        author: str,
        text: str,
        link: str | None,
    ) -> int | None:
        """Сохраняет сообщение и возвращает его id, либо None, если оно уже было сохранено."""
        async with self._conn.execute(
            "INSERT OR IGNORE INTO orders (chat_id, message_id, chat_title, author, text, link) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, message_id, chat_title, author, text, link),
        ) as cursor:
            await self._conn.commit()
            return cursor.lastrowid if cursor.rowcount else None

    async def skip_order(self, order_id: int) -> str | None:
        """Помечает заказ неинтересным и возвращает ссылку на исходное сообщение."""
        async with self._conn.execute(
            "UPDATE orders SET status = 'skipped' WHERE id = ? RETURNING link", (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
        await self._conn.commit()
        return row[0] if row else None