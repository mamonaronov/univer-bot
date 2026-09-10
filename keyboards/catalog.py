from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.queries import Link, Page

BUTTON_TITLE_LIMIT = 64
MAX_INLINE_BUTTONS = 96


def page_keyboard(
    page: Page,
    children: list[Page],
    links: list[Link],
    *,
    chunk_index: int,
    chunk_count: int,
    root_id: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for child in children:
        builder.row(
            InlineKeyboardButton(
                text=_label(child.title),
                callback_data=f"p:{child.id}:0",
            )
        )
    remaining = max(0, MAX_INLINE_BUTTONS - len(children) - 4)
    for link in links[:remaining]:
        builder.row(InlineKeyboardButton(text=_label(link.title), url=link.url))
    nav: list[InlineKeyboardButton] = []
    if chunk_index > 0:
        nav.append(
            InlineKeyboardButton(text="‹ стр.", callback_data=f"p:{page.id}:{chunk_index - 1}")
        )
    if chunk_index + 1 < chunk_count:
        nav.append(
            InlineKeyboardButton(text="стр. ›", callback_data=f"p:{page.id}:{chunk_index + 1}")
        )
    if nav:
        builder.row(*nav)
    bottom: list[InlineKeyboardButton] = []
    if page.parent_id is not None:
        bottom.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"p:{page.parent_id}:0"))
    if page.id != root_id:
        bottom.append(InlineKeyboardButton(text="В начало", callback_data=f"p:{root_id}:0"))
    if bottom:
        builder.row(*bottom)
    return builder.as_markup()


def _label(title: str) -> str:
    text = " ".join((title or "").split())
    if len(text) <= BUTTON_TITLE_LIMIT:
        return text or "—"
    return text[: BUTTON_TITLE_LIMIT - 1] + "…"
