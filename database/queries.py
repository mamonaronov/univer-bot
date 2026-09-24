"""Read-only catalog queries. Edit the SQLite file in DB Browser; no write path in the bot."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from database.db import Database

from services.synonyms import CAMPUS_MARKERS, expand, normalize

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

    async def search(self, query: str, limit: int = 5) -> list[Page]:
        """Поиск по title/body с синонимами. Возвращает Page, отсортированные по score."""
        words = expand(normalize(query))
        if not words:
            return []

        query_lower = query.lower()
        campus_boost_words: list[str] = []
        for marker, marker_words in CAMPUS_MARKERS.items():
            if marker in query_lower:
                campus_boost_words.extend(marker_words)

        conn = await self._conn()
        cur = await conn.execute(
            """
            SELECT id, parent_id, title, body, sort_order, source_url
            FROM pages
            WHERE is_visible = 1
            """
        )
        rows = await cur.fetchall()

        scored: list[tuple[int, Page]] = []
        for row in rows:
            title_l = (row["title"] or "").lower()
            body_l = (row["body"] or "").lower()

            score = 0
            for w in words:
                wl = w.lower()
                if wl in title_l:
                    score += 10
                elif wl in body_l:
                    score += 1

            for w in campus_boost_words:
                if w.lower() in body_l:
                    score += 5

            if score > 0:
                scored.append((score, Page(
                    id=row["id"],
                    parent_id=row["parent_id"],
                    title=row["title"] or "",
                    body=row["body"] or "",
                    sort_order=row["sort_order"],
                    source_url=row["source_url"],
                )))

        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [page for _, page in scored[:limit]]