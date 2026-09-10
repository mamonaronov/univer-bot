"""Talk to mihomo's local API. Telegram sessions must not share this HTTP client."""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

_KICK_COOLDOWN = 8.0


def next_proxy_name(current: str | None, nodes: object) -> str | None:
    """Return the node after *current* in *nodes*, wrapping around."""
    if not isinstance(nodes, list):
        return None
    names = [name for name in nodes if isinstance(name, str) and name.strip()]
    if not names:
        return None
    if not isinstance(current, str) or current not in names:
        return names[0]
    nxt = names[(names.index(current) + 1) % len(names)]
    if nxt == current:
        return None
    return nxt


class MihomoRotator:
    """Switch AUTO to the next node when getUpdates dies on a 'healthy' GET."""

    def __init__(
        self,
        api_url: str,
        secret: str | None,
        group: str = "AUTO",
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._secret = secret
        self._group = group
        self._lock = asyncio.Lock()
        self._last_kick = 0.0

    async def kick_current(self) -> None:
        if not self._secret:
            return
        async with self._lock:
            now = time.monotonic()
            if now - self._last_kick < _KICK_COOLDOWN:
                return
            self._last_kick = now
            try:
                await self._kick()
            except Exception:
                logger.exception("mihomo kick failed")

    async def _kick(self) -> None:
        headers = {"Authorization": f"Bearer {self._secret}"}
        timeout = aiohttp.ClientTimeout(total=4)
        group_url = f"{self._api_url}/proxies/{quote(self._group, safe='')}"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(group_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning("mihomo group http_%s", resp.status)
                    return
                data = await resp.json(content_type=None)
            current = data.get("now") if isinstance(data, dict) else None
            nxt = next_proxy_name(current if isinstance(current, str) else None, data.get("all") if isinstance(data, dict) else None)
            if nxt is None:
                logger.warning("mihomo has no next AUTO node current=%s", current)
                return
            async with session.put(group_url, headers=headers, json={"name": nxt}) as resp:
                logger.warning(
                    "mihomo switched %s -> %s status=%s",
                    current,
                    nxt,
                    resp.status,
                )
