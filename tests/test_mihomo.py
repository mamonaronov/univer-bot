from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from utils.mihomo import MihomoRotator, next_proxy_name
from utils.telegram_session import set_dead_proxy_handler


@pytest.mark.asyncio
async def test_rotator_skips_without_secret():
    rotator = MihomoRotator("http://127.0.0.1:19090", None)
    await rotator.kick_current()


@pytest.mark.asyncio
async def test_rotator_debounces(monkeypatch):
    rotator = MihomoRotator("http://127.0.0.1:19090", "secret")
    kick = AsyncMock()
    monkeypatch.setattr(rotator, "_kick", kick)
    await rotator.kick_current()
    await rotator.kick_current()
    assert kick.await_count == 1


def test_next_proxy_name_wraps():
    assert next_proxy_name("a", ["a", "b", "c"]) == "b"
    assert next_proxy_name("c", ["a", "b", "c"]) == "a"
    assert next_proxy_name("missing", ["a", "b"]) == "a"
    assert next_proxy_name("a", ["a"]) is None
    assert next_proxy_name("a", []) is None


def test_dead_proxy_handler_roundtrip():
    set_dead_proxy_handler(None)
    set_dead_proxy_handler(None)
