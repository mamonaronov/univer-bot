"""Probe Telegram through a session separate from polling."""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

from config import Config
from utils.telegram_session import make_telegram_session
from utils.timeouts import await_or_abandon, reset_bot_session

logger = logging.getLogger(__name__)


def make_probe_bot(config: Config) -> Bot:
    session = make_telegram_session(
        config.telegram_proxy_url,
        float(config.probe_timeout_seconds),
    )
    return Bot(token=config.bot_token, session=session)


async def measure_bot_latency(bot: Bot, timeout: float) -> tuple[bool, int, str | None]:
    started = time.monotonic()
    try:
        await await_or_abandon(bot.get_me(), timeout, name="probe.get_me")
        return True, int((time.monotonic() - started) * 1000), None
    except TimeoutError:
        latency_ms = int((time.monotonic() - started) * 1000)
        await reset_bot_session(bot)
        return False, latency_ms, "timeout"
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return False, latency_ms, f"{type(exc).__name__}: {exc}"[:300]


class TelegramProbe:
    """Periodic getMe on its own session. A hung ping cannot freeze polling."""

    def __init__(self, config: Config, probe_bot: Bot | None = None) -> None:
        self.config = config
        self._probe_bot = probe_bot or make_probe_bot(config)

    async def reset_probe(self) -> None:
        old = self._probe_bot
        self._probe_bot = make_probe_bot(self.config)
        await reset_bot_session(old)

    async def tick(self) -> None:
        ok, latency_ms, error = await measure_bot_latency(
            self._probe_bot, self.config.probe_timeout_seconds
        )
        if ok:
            logger.debug("telegram_probe_ok latency_ms=%s", latency_ms)
            return
        logger.warning("telegram_probe_fail latency_ms=%s error=%s", latency_ms, error)
        await self.reset_probe()

    async def run(self, stop: asyncio.Event) -> None:
        delay_ok = float(self.config.probe_interval_seconds)
        delay_fail = 5.0
        delay = delay_ok
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
                break
            except TimeoutError:
                pass
            try:
                await self.tick()
                delay = delay_ok
            except Exception:
                logger.exception("telegram probe tick failed")
                await self.reset_probe()
                delay = delay_fail
        await reset_bot_session(self._probe_bot)
