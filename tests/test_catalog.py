from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from catalog.seed import SCHEMA, _insert_link, _insert_page
from database.db import CatalogError, Database, ensure_catalog
from database.queries import Catalog


def test_ensure_catalog_requires_file(tmp_path: Path):
    db_path = tmp_path / "catalog.sqlite3"
    with pytest.raises(CatalogError, match="missing"):
        ensure_catalog(db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _insert_page(
        conn,
        parent_id=None,
        title="Корень",
        body="привет",
        sort_order=0,
        source_url="https://j-univer.ru/",
    )
    conn.commit()
    conn.close()
    ensure_catalog(db_path)


@pytest.mark.asyncio
async def test_catalog_tree(tmp_path: Path):
    db_path = tmp_path / "catalog.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    root = _insert_page(
        conn,
        parent_id=None,
        title="Еврейский университет",
        body="меню",
        sort_order=0,
        source_url="https://j-univer.ru/",
    )
    child = _insert_page(
        conn,
        parent_id=root,
        title="Контакты",
        body="телефон",
        sort_order=1,
        source_url="https://j-univer.ru/contact/",
    )
    _insert_link(conn, child, "Сайт", "https://j-univer.ru/contact/", 0)
    conn.execute("INSERT INTO meta(key, value) VALUES ('root_page_id', ?)", (str(root),))
    conn.commit()
    conn.close()

    db = Database(db_path)
    catalog = Catalog(db)
    assert await catalog.root_id() == root
    page = await catalog.get_page(child)
    assert page is not None
    assert page.title == "Контакты"
    kids = await catalog.children(root)
    assert [item.title for item in kids] == ["Контакты"]
    links = await catalog.links(child)
    assert links[0].url.endswith("/contact/")
    hidden = await catalog.get_page(999)
    assert hidden is None
    await db.close()
