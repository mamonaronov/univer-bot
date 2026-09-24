"""Поиск по ключевым словам: свободный текст → лучшая страница или меню."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from catalog.text import chunk_text, format_page
from database.queries import Catalog, Page
from keyboards.catalog import page_keyboard

logger = logging.getLogger(__name__)

router = Router(name="search")


@router.message(F.text & ~F.text.startswith("/"))
async def smart_search(message: Message, catalog: Catalog) -> None:
    query = (message.text or "").strip()
    if len(query) < 2:
        await _show_menu(message, catalog)
        return

    hits = await catalog.search(query)
    if not hits:
        logger.info("search miss chat_id=%s query=%r", message.chat.id, query)
        await _show_menu(message, catalog)
        return

    logger.info("search hit chat_id=%s query=%r page=%s", message.chat.id, query, hits[0].id)
    await _show_page(message, catalog, hits[0])


async def _show_menu(target: Message, catalog: Catalog) -> None:
    root = await catalog.get_page(await catalog.root_id())
    if root is None:
        await target.answer("Раздел не найден. Нажмите /start")
        return
    await _show_page(target, catalog, root)


async def _show_page(target: Message, catalog: Catalog, page: Page) -> None:
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