"""Telegram HTTP session that does not stall the bot when SOCKS ignores aiohttp timeouts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType

from utils.timeouts import await_or_abandon

logger = logging.getLogger(__name__)

_REQUEST_SLACK = 2.0
_GET_UPDATES_SLACK = 12.0
_CLOSE_TIMEOUT = 2.0
_SSL_CLOSE_PAUSE = 0.25

DeadProxyHandler = Callable[[], Awaitable[None]]
_dead_proxy_handler: DeadProxyHandler | None = None


def set_dead_proxy_handler(handler: DeadProxyHandler | None) -> None:
    global _dead_proxy_handler
    _dead_proxy_handler = handler


def request_wait_limit(
    method: TelegramMethod[TelegramType],
    session_timeout: float,
    timeout: Optional[int],
) -> float:
    """How long to wait before abandoning a Telegram HTTP call.

    aiogram passes ``session.timeout + polling_timeout`` for getUpdates so its
    own TimeoutError is not false-positive. That is too long for a hung SOCKS
    CONNECT: cap getUpdates at the long-poll window plus a short slack.
    """
    limit = float(session_timeout if timeout is None else timeout)
    api = getattr(method, "__api_method__", "") or ""
    if api != "getUpdates":
        return limit
    poll = float(getattr(method, "timeout", 0) or 0)
    cap = (poll + _GET_UPDATES_SLACK) if poll > 0 else float(session_timeout) + _GET_UPDATES_SLACK
    if limit <= 0:
        return cap
    return min(limit, cap)


def make_telegram_session(proxy_url: str | None, timeout: float) -> AiohttpSession:
    if proxy_url:
        return AbandonableAiohttpSession(proxy=proxy_url, timeout=timeout)
    return AbandonableAiohttpSession(timeout=timeout)


class AbandonableAiohttpSession(AiohttpSession):
    """Drop hung SOCKS connects so polling can retry instead of blocking forever."""

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        limit = request_wait_limit(method, float(self.timeout), timeout)
        name = f"telegram.{getattr(method, '__api_method__', type(method).__name__)}"
        if limit <= 0:
            return await super().make_request(bot, method, timeout)
        try:
            result = await await_or_abandon(
                super().make_request(bot, method, timeout),
                limit + _REQUEST_SLACK,
                name=name,
            )
        except TimeoutError as exc:
            await self.drop_connector()
            await _notify_dead_proxy()
            raise TelegramNetworkError(method=method, message="Request timeout error") from exc
        except TelegramConflictError:
            await self.drop_connector()
            raise
        except TelegramNetworkError:
            await self.drop_connector()
            await _notify_dead_proxy()
            raise
        api = getattr(method, "__api_method__", "") or ""
        if api == "getUpdates" and isinstance(result, list) and result:
            logger.info("getUpdates n=%s", len(result))
        return result

    async def drop_connector(self) -> None:
        old = self._session
        self._session = None
        self._should_reset_connector = True
        if old is None or getattr(old, "closed", True):
            return
        try:
            await await_or_abandon(old.close(), _CLOSE_TIMEOUT, name="telegram.session.close")
            await asyncio.sleep(_SSL_CLOSE_PAUSE)
        except TimeoutError:
            logger.warning("telegram session close hung, connector dropped")

    async def close(self) -> None:
        await self.drop_connector()


async def _notify_dead_proxy() -> None:
    handler = _dead_proxy_handler
    if handler is None:
        return
    try:
        await handler()
    except Exception:
        logger.exception("dead proxy handler failed")
