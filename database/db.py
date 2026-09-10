"""SQLite catalog: WAL, copy seed if the volume is empty."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


class CatalogError(RuntimeError):
    pass


def ensure_catalog(db_path: Path, seed_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and db_path.stat().st_size > 0:
        return
    if seed_path.exists() and seed_path.stat().st_size > 0:
        shutil.copy2(seed_path, db_path)
        logger.info("Copied seed catalog to %s", db_path)
        return
    raise CatalogError(
        f"Catalog DB is missing ({db_path}) and no seed file found at {seed_path}. "
        "Run: python -m catalog.seed"
    )


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA foreign_keys = ON")
            await self._conn.execute("PRAGMA journal_mode = WAL")
            await self._conn.execute("PRAGMA busy_timeout = 5000")
            logger.info("SQLite WAL mode confirmed")
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
