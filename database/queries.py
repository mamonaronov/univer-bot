"""Read-only catalog queries. Edit the SQLite file in DB Browser; no write path in the bot."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from database.db import Database


@dataclass(frozen=True, slots=True)
class Page:
    id: int
    parent_id: int | None
    title: str
    body: str
    sort_order: int
    source_url: str | None


@dataclass(frozen=True, slots=True)
class Link:
    id: int
    title: str
    url: str


class Catalog:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def _conn(self) -> aiosqlite.Connection:
        return await self._db.connect()

    async def meta(self, key: str) -> str | None:
        conn = await self._conn()
        cur = await conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = await cur.fetchone()
        return None if row is None else str(row["value"])

    async def root_id(self) -> int:
        raw = await self.meta("root_page_id")
        if raw:
            return int(raw)
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT id FROM pages WHERE parent_id IS NULL AND is_visible = 1 ORDER BY sort_order, id LIMIT 1"
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Catalog has no root page")
        return int(row["id"])

    async def get_page(self, page_id: int) -> Page | None:
        conn = await self._conn()
        cur = await conn.execute(
            """
            SELECT id, parent_id, title, body, sort_order, source_url
            FROM pages
            WHERE id = ? AND is_visible = 1
            """,
            (page_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return Page(
            id=row["id"],
            parent_id=row["parent_id"],
            title=row["title"],
            body=row["body"] or "",
            sort_order=row["sort_order"],
            source_url=row["source_url"],
        )

    async def children(self, parent_id: int) -> list[Page]:
        conn = await self._conn()
        cur = await conn.execute(
            """
            SELECT id, parent_id, title, body, sort_order, source_url
            FROM pages
            WHERE parent_id = ? AND is_visible = 1
            ORDER BY sort_order, id
            """,
            (parent_id,),
        )
        rows = await cur.fetchall()
        return [
            Page(
                id=row["id"],
                parent_id=row["parent_id"],
                title=row["title"],
                body=row["body"] or "",
                sort_order=row["sort_order"],
                source_url=row["source_url"],
            )
            for row in rows
        ]

    async def links(self, page_id: int) -> list[Link]:
        conn = await self._conn()
        cur = await conn.execute(
            """
            SELECT id, title, url
            FROM links
            WHERE page_id = ?
            ORDER BY sort_order, id
            """,
            (page_id,),
        )
        rows = await cur.fetchall()
        return [Link(id=row["id"], title=row["title"], url=row["url"]) for row in rows]
