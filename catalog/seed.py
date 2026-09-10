"""Download university pages and build a SQLite catalog that is easy to edit."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path

from catalog.html import decode_title, html_to_telegram, strip_self_and_child_nav

SITE = "https://j-univer.ru"
USER_AGENT = "univer-bot catalog seed/1.0 (+https://j-univer.ru/)"
SCHEMA_VERSION = "1"

# Keep the parent page, drop noisy children (room lists, staff-by-program, forms).
SKIP_DEEPER_THAN = (
    "/blog",
    "/form",
    "/news",
    "/sveden/employees/by_programm",
    "/sveden/employees/list",
    "/sveden/objects",
)

SKIP_SLUGS = {
    "ai-orange",
    "blog",
    "form",
    "news",
    "open-doors",
    "open-doors-sent",
    "app-study-sent",
    "programm_planed",
    "profilakticheskie-meroprijatija-po-predotvrashheniju-rasprostranenija-koronovirusa",
}

MAX_BODY_CHARS = 12000

ROOT_INTRO = (
    "<b>Еврейский университет</b>\n\n"
    "Справочник по официальному сайту j-univer.ru: поступление, учёба, "
    "факультеты и контакты.\n\n"
    "Выберите раздел."
)

SECTION_SPLIT_RE = re.compile(
    r"(?=<b>\s*\d+\.\s+[А-ЯЁA-Z])",
)
TITLE_CLEAN_RE = re.compile(r"<[^>]+>")


def _request(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.read(), headers


def fetch_json(url: str, retries: int = 4) -> tuple[object, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            raw, headers = _request(url)
            return json.loads(raw.decode("utf-8")), headers
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_all_pages() -> list[dict]:
    pages: list[dict] = []
    page_no = 1
    while True:
        url = (
            f"{SITE}/wp-json/wp/v2/pages?per_page=100&page={page_no}"
            "&_fields=id,link,title,parent,slug,content"
        )
        try:
            payload, headers = fetch_json(url)
        except RuntimeError as exc:
            if page_no > 1:
                break
            raise exc
        if not isinstance(payload, list) or not payload:
            break
        pages.extend(payload)
        total = int(headers.get("x-wp-totalpages") or headers.get("X-WP-TotalPages") or 1)
        if page_no >= total:
            break
        page_no += 1
    return pages


def _slug(item: dict) -> str:
    return unescape(str(item.get("slug") or ""))


def _path(item: dict) -> str:
    link = str(item.get("link") or "")
    return link.replace(SITE, "") or "/"


def keep_page(item: dict) -> bool:
    slug = _slug(item)
    path = _path(item).rstrip("/") or "/"
    if slug in SKIP_SLUGS:
        return False
    if path in {"/", "/ai-orange"}:
        return False
    for prefix in SKIP_DEEPER_THAN:
        if path == prefix or path.startswith(prefix + "/"):
            if path != prefix:
                return False
            if prefix in {"/blog", "/form", "/news"}:
                return False
    return True


def page_title(item: dict) -> str:
    raw = item.get("title") or {}
    rendered = raw.get("rendered") if isinstance(raw, dict) else str(raw)
    title = decode_title(rendered or "")
    title = title.replace("ОЧУ ВО «ЕВРЕЙСКИЙ УНИВЕРСИТЕТ»", "Еврейский университет")
    title = re.sub(r"\s+", " ", title).strip()
    return title[:80] or "Без названия"


def page_html(item: dict) -> str:
    content = item.get("content") or {}
    if isinstance(content, dict):
        return str(content.get("rendered") or "")
    return str(content or "")


def _truncate_body(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    cut = body[:MAX_BODY_CHARS]
    br = cut.rfind("\n\n")
    if br > MAX_BODY_CHARS // 2:
        cut = cut[:br]
    return cut.rstrip() + "\n\n<i>Текст сокращён.</i>"


def split_numbered_sections(title: str, body: str) -> list[tuple[str, str]]:
    if len(body) < 3500 or not SECTION_SPLIT_RE.search(body):
        return [(title, body)]
    parts = [part.strip() for part in SECTION_SPLIT_RE.split(body) if part.strip()]
    if len(parts) < 2:
        return [(title, body)]
    sections: list[tuple[str, str]] = []
    preamble = []
    for part in parts:
        plain = TITLE_CLEAN_RE.sub("", part).strip()
        first_line = plain.split("\n", 1)[0].strip()
        if re.match(r"^\d+\.\s+", first_line):
            heading = re.sub(r"^\d+\.\s+", "", first_line)
            heading = heading[:60]
            sections.append((heading, part))
        else:
            preamble.append(part)
    if not sections:
        return [(title, body)]
    result: list[tuple[str, str]] = []
    if preamble:
        result.append((title, "\n\n".join(preamble)))
    result.extend(sections)
    return result


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Дерево справочника. parent_id пустой — пункты главного меню.
-- is_visible: 1 показывать в боте, 0 скрыть (удобно снять галочку в DB Browser).
-- sort_order: меньше значение — выше кнопка.
-- body: HTML Telegram (<b>, <i>, mailto). Пустой body = только меню кнопок.
-- notes: комментарий редактора, бот его не показывает.
CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES pages(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_visible INTEGER NOT NULL DEFAULT 1,
    source_url TEXT,
    notes TEXT
);

-- Необязательные URL-кнопки, если редактор добавит их вручную.
CREATE TABLE links (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_pages_parent ON pages(parent_id, sort_order, id);
CREATE INDEX idx_links_page ON links(page_id, sort_order, id);
"""

TOP_ORDER = [
    "about",
    "applicants",
    "students",
    "science",
    "prog",
    "sveden",
    "contact",
    "nashi-partnery",
]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def _insert_page(
    conn: sqlite3.Connection,
    *,
    parent_id: int | None,
    title: str,
    body: str,
    sort_order: int,
    source_url: str | None,
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO pages (parent_id, title, body, sort_order, is_visible, source_url, notes)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """,
        (parent_id, title, _truncate_body(body), sort_order, source_url, notes),
    )
    return int(cur.lastrowid)


def _insert_link(conn: sqlite3.Connection, page_id: int, title: str, url: str, sort_order: int) -> None:
    conn.execute(
        "INSERT INTO links (page_id, title, url, sort_order) VALUES (?, ?, ?, ?)",
        (page_id, title, url, sort_order),
    )


def build_catalog(conn: sqlite3.Connection, wp_pages: list[dict]) -> None:
    kept = [item for item in wp_pages if keep_page(item)]
    children: dict[int, list[dict]] = {}
    for item in kept:
        parent = int(item.get("parent") or 0)
        children.setdefault(parent, []).append(item)

    intro = ROOT_INTRO

    root_id = _insert_page(
        conn,
        parent_id=None,
        title="Еврейский университет",
        body=intro,
        sort_order=0,
        source_url=SITE + "/",
        notes="Корневое меню. parent_id пустой.",
    )

    def sort_key(item: dict) -> tuple[int, str]:
        slug = _slug(item)
        if slug in TOP_ORDER:
            return (TOP_ORDER.index(slug), page_title(item).lower())
        return (100 + int(item.get("id") or 0), page_title(item).lower())

    def walk(wp_parent: int, db_parent: int) -> None:
        items = sorted(children.get(wp_parent, []), key=sort_key)
        for index, item in enumerate(items, start=1):
            wp_id = int(item["id"])
            title = page_title(item)
            url = str(item.get("link") or "")
            raw = page_html(item)
            child_titles = [page_title(child) for child in children.get(wp_id, [])]
            body = strip_self_and_child_nav(
                html_to_telegram(raw, url),
                title,
                child_titles,
            )
            notes = f"wordpress_id={wp_id}; slug={_slug(item)}"
            sections = split_numbered_sections(title, body)
            if len(sections) == 1:
                db_id = _insert_page(
                    conn,
                    parent_id=db_parent,
                    title=title,
                    body=sections[0][1],
                    sort_order=index,
                    source_url=url,
                    notes=notes,
                )
            else:
                overview_body = sections[0][1] if sections[0][0] == title else ""
                rest = sections[1:] if sections[0][0] == title else sections
                if sections[0][0] != title:
                    overview_body = ""
                    rest = sections
                db_id = _insert_page(
                    conn,
                    parent_id=db_parent,
                    title=title,
                    body=overview_body,
                    sort_order=index,
                    source_url=url,
                    notes=notes,
                )
                for sub_index, (sub_title, sub_body) in enumerate(rest, start=1):
                    _insert_page(
                        conn,
                        parent_id=db_id,
                        title=sub_title,
                        body=sub_body,
                        sort_order=sub_index,
                        source_url=url,
                        notes=f"split from wordpress_id={wp_id}",
                    )
            walk(wp_id, db_id)

    walk(0, root_id)

    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?), (?, ?), (?, ?), (?, ?)",
        (
            "schema_version",
            SCHEMA_VERSION,
            "root_page_id",
            str(root_id),
            "source_site",
            SITE,
            "page_count",
            str(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]),
        ),
    )
    conn.commit()


def seed(db_path: Path) -> None:
    print(f"Fetching pages from {SITE} ...", flush=True)
    wp_pages = fetch_all_pages()
    print(f"Got {len(wp_pages)} WordPress pages", flush=True)
    conn = _connect(db_path)
    try:
        build_catalog(conn, wp_pages)
        pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        links = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        print(f"Wrote {db_path}: {pages} pages, {links} links", flush=True)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    target = Path(args[0]) if args else Path("data/catalog.seed.sqlite3")
    seed(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
