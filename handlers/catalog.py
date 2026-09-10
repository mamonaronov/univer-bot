from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from catalog.text import chunk_text, format_page
from database.queries import Catalog
from keyboards.catalog import page_keyboard

logger = logging.getLogger(__name__)

router = Router(name="catalog")


def setup_routers() -> Router:
    root = Router()
    root.include_router(router)
    return root


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, catalog: Catalog) -> None:
    logger.info("command /start chat_id=%s", message.chat.id)
    root_id = await catalog.root_id()
    await _send_page(message, catalog, root_id, 0, edit=False)


@router.message()
async def any_text(message: Message, catalog: Catalog) -> None:
    logger.info("message chat_id=%s", message.chat.id)
    root_id = await catalog.root_id()
    await _send_page(message, catalog, root_id, 0, edit=False)


@router.callback_query(F.data.startswith("p:"))
async def open_page(callback: CallbackQuery, catalog: Catalog) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    logger.info("callback page=%s chat_id=%s", parts[1], callback.message.chat.id)
    await _send_page(callback.message, catalog, int(parts[1]), int(parts[2]), edit=True)
    await callback.answer()


async def _send_page(
    target: Message,
    catalog: Catalog,
    page_id: int,
    chunk_index: int,
    *,
    edit: bool,
) -> None:
    page = await catalog.get_page(page_id)
    if page is None:
        await _deliver(target, "Раздел не найден. Нажмите /start", None, edit=False)
        return
    root_id = await catalog.root_id()
    children = await catalog.children(page.id)
    links = await catalog.links(page.id)
    chunks = chunk_text(page.body)
    if chunk_index >= len(chunks):
        chunk_index = 0
    text = format_page(page.title, chunks[chunk_index], chunk_index, len(chunks))
    markup = page_keyboard(
        page,
        children,
        links,
        chunk_index=chunk_index,
        chunk_count=len(chunks),
        root_id=root_id,
    )
    await _deliver(target, text, markup, edit=edit)


async def _deliver(target: Message, text: str, markup, *, edit: bool) -> None:
    try:
        await _emit(target, text, markup, edit=edit, parse_mode=ParseMode.HTML)
        return
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        logger.warning("HTML send failed: %s", exc)
    plain = html.escape(_strip_tags(text) or "Откройте раздел кнопками ниже.")
    try:
        await _emit(target, plain, markup, edit=edit, parse_mode=ParseMode.HTML)
        return
    except TelegramBadRequest as exc:
        logger.warning("plain send failed: %s", exc)
    try:
        await target.answer("Не удалось показать раздел. Нажмите /start")
    except Exception:
        logger.exception("Failed to send fallback message")


async def _emit(target: Message, text: str, markup, *, edit: bool, parse_mode: ParseMode) -> None:
    if edit:
        await target.edit_text(
            text,
            reply_markup=markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return
    await target.answer(
        text,
        reply_markup=markup,
        parse_mode=parse_mode,
        disable_web_page_preview=True,
    )


def _strip_tags(text: str) -> str:
    out = []
    in_tag = False
    for char in text:
        if char == "<":
            in_tag = True
            continue
        if char == ">":
            in_tag = False
            continue
        if not in_tag:
            out.append(char)
    return (
        "".join(out)
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
