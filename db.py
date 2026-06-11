"""SQLite-backed message store with full-text search (FTS5).

We use SQLite's built-in FTS5 so the bot is fully self-contained — no external
vector database or embeddings service is required. Message content is indexed
for full-text search; metadata (author, channel, etc.) is stored alongside it.
"""

import re

import aiosqlite

CREATE_MESSAGES_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages USING fts5(
    message_id UNINDEXED,
    guild_id UNINDEXED,
    channel_id UNINDEXED,
    channel_name UNINDEXED,
    author_id UNINDEXED,
    author_name UNINDEXED,
    content,
    created_at UNINDEXED,
    tokenize = 'porter unicode61'
);
"""

CREATE_OPTOUT_SQL = """
CREATE TABLE IF NOT EXISTS opted_out (
    user_id TEXT PRIMARY KEY
);
"""

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def build_match_query(text: str) -> str:
    """Turn free-form user text into a safe FTS5 MATCH query.

    We extract word tokens and OR them together, quoting each one so that FTS5
    operators in user input (AND, OR, NEAR, quotes, etc.) can't break the query.
    """
    tokens = _WORD_RE.findall(text)
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens)


class Database:
    def __init__(self, path: str):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        await self._db.execute(CREATE_MESSAGES_SQL)
        await self._db.execute(CREATE_OPTOUT_SQL)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()

    async def is_opted_out(self, user_id) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM opted_out WHERE user_id = ?", (str(user_id),)
        ) as cur:
            return await cur.fetchone() is not None

    async def opt_out(self, user_id) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO opted_out (user_id) VALUES (?)", (str(user_id),)
        )
        # Also delete anything we already stored for this user.
        await self._db.execute(
            "DELETE FROM messages WHERE author_id = ?", (str(user_id),)
        )
        await self._db.commit()

    async def opt_in(self, user_id) -> None:
        await self._db.execute(
            "DELETE FROM opted_out WHERE user_id = ?", (str(user_id),)
        )
        await self._db.commit()

    async def store_message(
        self,
        *,
        message_id,
        guild_id,
        channel_id,
        channel_name,
        author_id,
        author_name,
        content,
        created_at,
    ) -> None:
        await self._db.execute(
            "INSERT INTO messages "
            "(message_id, guild_id, channel_id, channel_name, author_id, "
            "author_name, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(message_id),
                str(guild_id),
                str(channel_id),
                channel_name,
                str(author_id),
                author_name,
                content,
                created_at,
            ),
        )
        await self._db.commit()

    async def search(self, guild_id, query_text: str, limit: int = 12):
        """Return the most relevant stored messages for a query, newest-rank first."""
        match = build_match_query(query_text)
        if not match:
            return []
        sql = (
            "SELECT channel_name, author_name, content, created_at "
            "FROM messages "
            "WHERE guild_id = ? AND messages MATCH ? "
            "ORDER BY rank "
            "LIMIT ?"
        )
        async with self._db.execute(sql, (str(guild_id), match, limit)) as cur:
            return await cur.fetchall()
