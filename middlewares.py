from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database.queries import Catalog

logger = logging.getLogger(__name__)


class UpdateLogMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            kind = event.event_type if hasattr(event, "event_type") else type(event).__name__
            logger.info("update id=%s type=%s", event.update_id, kind)
        return await handler(event, data)


class CatalogMiddleware(BaseMiddleware):
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["catalog"] = self.catalog
        return await handler(event, data)
