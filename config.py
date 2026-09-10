"""Service configuration from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
_SECRET_RE = re.compile(r'(?m)^secret:\s*"([^"]+)"')


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    return Path(raw) if raw else default


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    db_path: Path
    seed_db_path: Path
    log_level: str
    telegram_proxy_url: str | None
    probe_interval_seconds: int
    probe_timeout_seconds: int
    mihomo_api_url: str
    mihomo_api_secret: str | None
    mihomo_proxy_group: str


def _mihomo_secret() -> str | None:
    env = _optional("MIHOMO_API_SECRET")
    if env:
        return env
    for path in (
        Path("/app/mihomo/config.yaml"),
        PROJECT_ROOT / "deploy/mihomo/config.yaml",
    ):
        if not path.is_file():
            continue
        match = _SECRET_RE.search(path.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return None


def load_config() -> Config:
    load_dotenv()
    token = _require("BOT_TOKEN")
    return Config(
        bot_token=token,
        db_path=_path("DB_PATH", PROJECT_ROOT / "data/catalog.sqlite3"),
        seed_db_path=_path("SEED_DB_PATH", PROJECT_ROOT / "data/catalog.sqlite3"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        telegram_proxy_url=_optional("TELEGRAM_PROXY_URL"),
        probe_interval_seconds=max(5, _int("PROBE_INTERVAL_SECONDS", 30)),
        probe_timeout_seconds=max(2, _int("PROBE_TIMEOUT_SECONDS", 8)),
        mihomo_api_url=os.getenv("MIHOMO_API_URL", "http://127.0.0.1:19090").strip()
        or "http://127.0.0.1:19090",
        mihomo_api_secret=_mihomo_secret(),
        mihomo_proxy_group=os.getenv("MIHOMO_PROXY_GROUP", "AUTO").strip() or "AUTO",
    )
