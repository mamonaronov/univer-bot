from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aiogram.client.session.aiohttp import AiohttpSession

from config import Config
from services.health import make_probe_bot
from utils.telegram_session import AbandonableAiohttpSession, make_telegram_session


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token="123456:ABC",
        db_path=tmp_path / "catalog.sqlite3",
        log_level="INFO",
        telegram_proxy_url="socks5://127.0.0.1:11808",
        probe_interval_seconds=30,
        probe_timeout_seconds=8,
        mihomo_api_url="http://127.0.0.1:19090",
        mihomo_api_secret="secret",
        mihomo_proxy_group="AUTO",
    )


def test_probe_bot_is_not_the_polling_session(tmp_path):
    config = _config(tmp_path)
    polling = make_telegram_session(config.telegram_proxy_url, 60)
    probe = make_probe_bot(config)
    assert isinstance(probe.session, AiohttpSession)
    assert isinstance(probe.session, AbandonableAiohttpSession)
    assert probe.session is not polling
    assert probe.session.proxy == "socks5://127.0.0.1:11808"
    assert probe.session.timeout == 8.0
    assert probe.token == config.bot_token
    assert replace(config, telegram_proxy_url=None).telegram_proxy_url is None
