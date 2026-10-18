import time

from fastapi.testclient import TestClient

from cryptoagent.config import get_config, get_secrets
from cryptoagent.market.exchange import _klines_to_df, perp_symbol


def test_klines_parsing_drops_open_candle():
    now = int(time.time() * 1000)
    hour = 3_600_000
    t0 = now - now % hour - 3 * hour
    row = lambda t: [t, "1", "2", "0.5", "1.5", "100", t + hour - 1, "150", 10, "60", "90", "0"]  # noqa: E731
    df = _klines_to_df([row(t0), row(t0 + hour), row(t0 + 2 * hour), row(t0 + 3 * hour)], "1h")
    assert len(df) == 3  # la última vela sigue abierta
    assert df["taker_buy_volume"].iloc[0] == 60.0 and df["close"].iloc[0] == 1.5
    assert str(df.index.tz) == "UTC"
    assert perp_symbol("BTC/USDT") == "BTC/USDT:USDT"


def test_api_auth_and_health(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("API_TOKEN", "secreto")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/api.db")
    get_secrets.cache_clear()
    get_config.cache_clear()
    from cryptoagent.api.server import app

    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert c.get("/market").status_code == 401
        assert c.get("/market", headers={"Authorization": "Bearer malo"}).status_code == 401
        r = c.get("/market", headers={"Authorization": "Bearer secreto"})
        assert r.status_code == 200 and r.json()["signals"] == []
        assert c.get("/symbol/BTC", headers={"Authorization": "Bearer secreto"}).status_code == 404
        assert c.get("/signals", headers={"Authorization": "Bearer secreto"}).json() == []
    get_secrets.cache_clear()
    get_config.cache_clear()
