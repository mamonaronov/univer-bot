"""Split catalog text into Telegram-sized chunks without breaking HTML tags."""

from __future__ import annotations

import re

TELEGRAM_LIMIT = 4096
# Leave room for the title line prepended by the handler.
CHUNK_LIMIT = 3500

_PARAGRAPH_RE = re.compile(r"\n{2,}")


def chunk_text(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    body = (text or "").strip()
    if not body:
        return [""]
    if len(body) <= limit:
        return [body]
    parts = _PARAGRAPH_RE.split(body)
    chunks: list[str] = []
    current = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        candidate = piece if not current else f"{current}\n\n{piece}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(piece) <= limit:
            current = piece
            continue
        chunks.extend(_split_hard(piece, limit))
    if current:
        chunks.append(current)
    return chunks or [""]


def _split_hard(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        window = rest[:limit]
        cut = window.rfind("\n")
        if cut < limit // 3:
            cut = window.rfind(" ")
        if cut < limit // 3:
            cut = limit
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [c for c in chunks if c]


def format_page(title: str, body: str, chunk_index: int, chunk_count: int) -> str:
    header = f"<b>{_escape_title(title)}</b>"
    if chunk_count > 1:
        header = f"{header}\n<i>стр. {chunk_index + 1}/{chunk_count}</i>"
    body = body.strip()
    if not body:
        return header
    return f"{header}\n\n{body}"


def _escape_title(title: str) -> str:
    return (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
