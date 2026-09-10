from config import load_config


def test_telegram_proxy_optional(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "")
    monkeypatch.delenv("SEED_DB_PATH", raising=False)
    cfg = load_config()
    assert cfg.telegram_proxy_url is None
    assert cfg.bot_token == "123:abc"


def test_telegram_proxy_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://127.0.0.1:11808")
    cfg = load_config()
    assert cfg.telegram_proxy_url == "socks5://127.0.0.1:11808"
