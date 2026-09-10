from config import load_config


def test_telegram_proxy_optional(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "")
    cfg = load_config()
    assert cfg.telegram_proxy_url is None
    assert cfg.bot_token == "123:abc"


def test_telegram_proxy_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://127.0.0.1:11808")
    cfg = load_config()
    assert cfg.telegram_proxy_url == "socks5://127.0.0.1:11808"


def test_default_db_is_repo_catalog(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("DB_PATH", "")
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "")
    cfg = load_config()
    assert cfg.db_path.name == "catalog.sqlite3"
    assert cfg.db_path.parent.name == "data"
