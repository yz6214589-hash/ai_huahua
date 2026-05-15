from core.db import load_mysql_config


def test_load_mysql_config_from_wucai_env(monkeypatch) -> None:
    monkeypatch.setenv("WUCAI_SQL_HOST", "127.0.0.9")
    monkeypatch.setenv("WUCAI_SQL_PORT", "3307")
    monkeypatch.setenv("WUCAI_SQL_USERNAME", "u1")
    monkeypatch.setenv("WUCAI_SQL_PASSWORD", "p1")
    monkeypatch.setenv("WUCAI_SQL_DB", "db1")

    cfg = load_mysql_config()
    assert cfg.host == "127.0.0.9"
    assert cfg.port == 3307
    assert cfg.user == "u1"
    assert cfg.password == "p1"
    assert cfg.database == "db1"

