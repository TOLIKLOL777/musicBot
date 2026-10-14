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

CREATE TABLE IF NOT EXISTS allowed_chats (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL UNIQUE,
    chat_title TEXT,
    username TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('notifications', 1);
"""


class Database:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn
        self._notifications_enabled = True
        self._keywords: tuple[str, ...] = ()
        self._allowed_chat_ids: set[int] = set()
        self._order_count = 0

    @classmethod
    async def connect(cls, path: str) -> "Database":
        conn = await aiosqlite.connect(path)
        async with conn.execute("PRAGMA journal_mode = WAL"):
            pass
        async with conn.execute("PRAGMA synchronous = NORMAL"):
            pass
        async with conn.execute("PRAGMA busy_timeout = 5000"):
            pass
        await conn.executescript(SCHEMA)
        await conn.commit()
        database = cls(conn)
        await database._refresh_watch_cache()
        async with conn.execute("SELECT COUNT(*) FROM orders") as cursor:
            database._order_count = (await cursor.fetchone())[0]
        return database

    async def close(self) -> None:
        await self._conn.close()

    async def _refresh_watch_cache(self) -> None:
        async with self._conn.execute(
            "SELECT value FROM settings WHERE key = 'notifications'"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Настройка уведомлений отсутствует в базе данных.")
        self._notifications_enabled = bool(row[0])

        async with self._conn.execute("SELECT word FROM keywords") as cursor:
            self._keywords = tuple(row[0].lower() for row in await cursor.fetchall())

        async with self._conn.execute("SELECT chat_id FROM allowed_chats") as cursor:
            self._allowed_chat_ids = {row[0] for row in await cursor.fetchall()}

    def should_notify_for_message(self, chat_id: int, text: str) -> bool:
        if not self._notifications_enabled:
            return False
        if self._allowed_chat_ids and chat_id not in self._allowed_chat_ids:
            return False

        lowered = text.lower()
        return any(word in lowered for word in self._keywords)

    async def dashboard_stats(self) -> tuple[int, int, int, bool]:
        async with self._conn.execute("SELECT COUNT(*) FROM orders") as cursor:
            self._order_count = (await cursor.fetchone())[0]
        return (
            self._order_count,
            len(self._keywords),
            len(self._allowed_chat_ids),
            self._notifications_enabled,
        )

    async def keywords(self) -> list[tuple[int, str]]:
        async with self._conn.execute("SELECT id, word FROM keywords ORDER BY word") as cursor:
            return [(row[0], row[1]) for row in await cursor.fetchall()]

    async def add_keyword(self, word: str) -> None:
        await self.add_keywords([word])

    async def add_keywords(self, words: list[str]) -> None:
        if not words:
            return
        await self._conn.executemany(
            "INSERT OR IGNORE INTO keywords (word) VALUES (?)",
            [(word,) for word in words],
        )
        await self._conn.commit()
        await self._refresh_watch_cache()

    async def delete_keyword(self, keyword_id: int) -> None:
        await self._conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        await self._conn.commit()
        await self._refresh_watch_cache()

    async def notifications_enabled(self) -> bool:
        return self._notifications_enabled

    async def allowed_chats(self) -> list[tuple[int, int, str | None, str | None]]:
        async with self._conn.execute(
            "SELECT id, chat_id, chat_title, username FROM allowed_chats ORDER BY chat_title, chat_id"
        ) as cursor:
            return [(row[0], row[1], row[2], row[3]) for row in await cursor.fetchall()]

    async def add_allowed_chat(
        self, chat_id: int, chat_title: str | None = None, username: str | None = None
    ) -> None:
        await self._conn.execute(
            "INSERT INTO allowed_chats (chat_id, chat_title, username) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET chat_title = excluded.chat_title, username = excluded.username",
            (chat_id, chat_title, username),
        )
        await self._conn.commit()
        self._allowed_chat_ids.add(chat_id)

    async def delete_allowed_chat(self, chat_id: int) -> None:
        await self._conn.execute("DELETE FROM allowed_chats WHERE chat_id = ?", (chat_id,))
        await self._conn.commit()
        self._allowed_chat_ids.discard(chat_id)

    async def is_chat_allowed(self, chat_id: int) -> bool:
        return not self._allowed_chat_ids or chat_id in self._allowed_chat_ids

    async def toggle_notifications(self) -> None:
        await self._conn.execute(
            "UPDATE settings SET value = 1 - value WHERE key = 'notifications'"
        )
        await self._conn.commit()
        self._notifications_enabled = not self._notifications_enabled

    async def add_order(
        self,
        chat_id: int,
        message_id: int,
        chat_title: str,
        author: str,
        text: str,
        link: str | None,
    ) -> int | None:
        """Сохраняет сообщение и возвращает его id, либо None, если оно уже было сохранено"""
        async with self._conn.execute(
            "INSERT OR IGNORE INTO orders (chat_id, message_id, chat_title, author, text, link) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, message_id, chat_title, author, text, link),
        ) as cursor:
            await self._conn.commit()
            order_id = cursor.lastrowid if cursor.rowcount else None
        if order_id is not None:
            self._order_count += 1
        return order_id

    async def skip_order(self, order_id: int) -> str | None:
        """Помечает заказ неинтересным и возвращает ссылку на исходное сообщение"""
        async with self._conn.execute(
            "UPDATE orders SET status = 'skipped' WHERE id = ? RETURNING link", (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
        await self._conn.commit()
        return row[0] if row else None

    async def orders(
        self, limit: int, offset: int
    ) -> tuple[list[tuple[int, str, str, str, str | None, str, str]], int]:
        async with self._conn.execute(
            "SELECT id, chat_title, author, text, link, status, created_at "
            "FROM orders ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()

        async with self._conn.execute("SELECT COUNT(*) FROM orders") as cursor:
            self._order_count = (await cursor.fetchone())[0]
        return rows, self._order_count

    async def delete_order(self, order_id: int) -> bool:
        async with self._conn.execute("DELETE FROM orders WHERE id = ?", (order_id,)) as cursor:
            deleted = cursor.rowcount > 0
        await self._conn.commit()
        if deleted:
            self._order_count -= 1
        return deleted