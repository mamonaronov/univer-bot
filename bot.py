"""University handbook bot. One polling session through the local mihomo SOCKS proxy."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BotCommand

from config import ConfigError, load_config
from database.db import CatalogError, Database, ensure_catalog
from database.queries import Catalog
from handlers import setup_routers
from middlewares import CatalogMiddleware, UpdateLogMiddleware
from utils.logging import setup_logging
from utils.mihomo import MihomoRotator
from utils.telegram_session import make_telegram_session, set_dead_proxy_handler
from utils.timeouts import await_or_abandon, reset_bot_session

logger = logging.getLogger("bot")

_POLLING_RETRY_INITIAL = 2.0
_POLLING_RETRY_MAX = 30.0
_POLLING_SESSION_TIMEOUT = 60.0
_POLLING_LONG_POLL = 20
_STARTUP_GET_ME_TIMEOUT = 20.0


def _make_session(proxy_url: str | None):
    return make_telegram_session(proxy_url, _POLLING_SESSION_TIMEOUT)


def _bot_session(proxy_url: str | None):
    if not proxy_url:
        logger.info("telegram_proxy_disabled")
    try:
        session = _make_session(proxy_url)
    except ImportError as exc:
        raise ConfigError("TELEGRAM_PROXY_URL is set but aiohttp-socks is not installed") from exc
    if proxy_url:
        logger.info("telegram_proxy_enabled")
    return session


async def _recycle_bot_session(bot: Bot, proxy_url: str | None) -> None:
    await reset_bot_session(bot)
    try:
        bot.session = _make_session(proxy_url)
    except Exception:
        logger.exception("Failed to recreate bot session")


async def _wait_until_telegram_ready(
    bot: Bot,
    stop: asyncio.Event,
    proxy_url: str | None,
    *,
    attempt_timeout: float = _STARTUP_GET_ME_TIMEOUT,
    initial_delay: float = _POLLING_RETRY_INITIAL,
    max_delay: float = _POLLING_RETRY_MAX,
) -> bool:
    delay = initial_delay
    while not stop.is_set():
        try:
            await await_or_abandon(bot.me(), attempt_timeout, name="startup.get_me")
            logger.info("Telegram API reachable")
            return True
        except (TimeoutError, TelegramNetworkError) as exc:
            logger.warning("Telegram not reachable, retry in %.0fs: %s", delay, exc)
        except Exception:
            logger.exception("Telegram handshake failed")
        await _recycle_bot_session(bot, proxy_url)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
            return False
        except TimeoutError:
            delay = min(delay * 2, max_delay)
    return False


async def _start_polling_with_retry(
    dp: Dispatcher,
    bot: Bot,
    stop: asyncio.Event,
    *,
    proxy_url: str | None = None,
    initial_delay: float = _POLLING_RETRY_INITIAL,
    max_delay: float = _POLLING_RETRY_MAX,
) -> None:
    delay = initial_delay
    while not stop.is_set():
        try:
            await dp.start_polling(
                bot,
                polling_timeout=_POLLING_LONG_POLL,
                allowed_updates=["message", "callback_query"],
                handle_signals=False,
                close_bot_session=False,
                drop_pending_updates=False,
            )
            return
        except (TelegramNetworkError, TimeoutError) as exc:
            logger.warning("Telegram network error, retry in %.0fs: %s", delay, exc)
            await _recycle_bot_session(bot, proxy_url)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
                return
            except TimeoutError:
                delay = min(delay * 2, max_delay)


async def run() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(config.log_level)
    logger.info("Starting univer-bot")
    rotator = MihomoRotator(
        config.mihomo_api_url,
        config.mihomo_api_secret,
        config.mihomo_proxy_group,
    )
    set_dead_proxy_handler(rotator.kick_current)

    try:
        ensure_catalog(config.db_path)
        session = _bot_session(config.telegram_proxy_url)
    except (ConfigError, CatalogError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    db = Database(config.db_path)
    catalog = Catalog(db)
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher()
    dp.update.outer_middleware(UpdateLogMiddleware())
    dp.update.outer_middleware(CatalogMiddleware(catalog))
    dp.include_router(setup_routers())

    @dp.error()
    async def _on_error(event) -> None:
        logger.exception("Dispatcher error: %s", getattr(event, "exception", event))

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _ask_stop() -> None:
        stop.set()
        loop.create_task(dp.stop_polling())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _ask_stop)
        except NotImplementedError:
            pass

    await db.connect()

    logger.info("Waiting for Telegram API")
    telegram_ok = await _wait_until_telegram_ready(bot, stop, config.telegram_proxy_url)
    if stop.is_set() or not telegram_ok:
        await reset_bot_session(bot)
        await db.close()
        return

    me = await bot.me()
    logger.info("Telegram bot @%s id=%s", me.username, me.id)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        logger.exception("Failed to delete webhook")

    @dp.startup.register
    async def _on_bot_ready() -> None:
        logger.info("Polling started @%s", me.username)
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Открыть справочник"),
                    BotCommand(command="menu", description="Главное меню"),
                ]
            )
        except Exception:
            logger.exception("Failed to set bot commands")

    try:
        await _start_polling_with_retry(dp, bot, stop, proxy_url=config.telegram_proxy_url)
    finally:
        stop.set()
        try:
            await bot.session.close()
        except Exception:
            logger.exception("Bot session close failed")
        await db.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except Exception:
        logging.getLogger("bot").exception("Fatal error")
        raise SystemExit(1)
