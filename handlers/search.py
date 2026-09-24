"""Поиск по ключевым словам: свободный текст → страница, варианты или меню."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from catalog.text import chunk_text, format_page
from database.queries import Catalog, Page
from keyboards.catalog import page_keyboard

logger = logging.getLogger(__name__)

router = Router(name="search")

# Сколько дополнительных вариантов показывать кнопками под найденной страницей.
MAX_ALTERNATIVES = 2


@router.message(F.text & ~F.text.startswith("/"))
async def smart_search(message: Message, catalog: Catalog) -> None:
    query = (message.text or "").strip()
    if len(query) < 2:
        await _show_menu(message, catalog, reason=None)
        return

    hits = await catalog.search(query, limit=MAX_ALTERNATIVES + 1)
    if not hits:
        logger.info("search miss chat_id=%s query=%r", message.chat.id, query)
        await _show_menu(message, catalog, reason=query)
        return

    logger.info(
        "search hit chat_id=%s query=%r page=%s alternatives=%d",
        message.chat.id, query, hits[0].id, len(hits) - 1,
    )
    await _show_page(message, catalog, hits[0], alternatives=hits[1:])


async def _show_menu(target: Message, catalog: Catalog, reason: str | None) -> None:
    root = await catalog.get_page(await catalog.root_id())
    if root is None:
        await target.answer("Раздел не найден. Нажмите /start")
        return
    if reason:
        await target.answer(
            f"По запросу «{html.escape(reason)}» ничего не нашёл.\n"
            "Вот меню — выберите раздел или переформулируйте запрос:"
        )
    await _show_page(target, catalog, root, alternatives=[])


async def _show_page(
    target: Message,
    catalog: Catalog,
    page: Page,
    *,
    alternatives: list[Page],
) -> None:
    root_id = await catalog.root_id()
    children = await catalog.children(page.id)
    links = await catalog.links(page.id)
    chunks = chunk_text(page.body)
    text = format_page(page.title, chunks[0], 0, len(chunks))

    markup = page_keyboard(
        page,
        children,
        links,
        chunk_index=0,
        chunk_count=len(chunks),
        root_id=root_id,
    )

    if alternatives:
        markup = _with_alternatives(markup, alternatives)

    try:
        await target.answer(
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as exc:
        logger.warning("search HTML send failed: %s", exc)
        await target.answer(html.escape(page.title or "Раздел"))


def _with_alternatives(
    markup: InlineKeyboardMarkup,
    alternatives: list[Page],
) -> InlineKeyboardMarkup:
    """Добавляет сверху ряд кнопок «возможно, вы искали»."""
    builder = InlineKeyboardBuilder()
    for alt in alternatives:
        builder.row(InlineKeyboardButton(
            text=_short(alt.title),
            callback_data=f"p:{alt.id}:0",
        ))
    # Кнопки из исходной клавиатуры переносим ниже.
    for row in markup.inline_keyboard:
        builder.row(*row)
    return builder.as_markup()


def _short(title: str, limit: int = 40) -> str:
    text = " ".join((title or "").split())
    if len(text) <= limit:
        return text or "—"
    return text[: limit - 1] + "…"