import asyncio
import datetime as dt

import pandas as pd
from sqlalchemy import select

import cryptoagent.agent.orchestrator as orch
from cryptoagent.agent.evaluation import outcome_from_path, performance_summary, update_component_stats
from cryptoagent.config import AgentConfig, Secrets
from cryptoagent.notify.telegram import _chunks
from cryptoagent.storage.db import ComponentStat, Database, Signal

from .conftest import FakeMarketData, make_derivs


def _agent(tmp_path, monkeypatch, sent):
    async def fake_derivs(md, symbol, period="1h", limit=500):
        perp = await md.candles(symbol, period, 400, market="perp")
        return make_derivs(perp)

    async def fake_macro():
        return {"fear_greed": {"value": 55, "label": "Greed", "hace_7d": 40}}

    monkeypatch.setattr(orch, "fetch_derivatives", fake_derivs)
    monkeypatch.setattr(orch, "fetch_macro", fake_macro)
    sec = Secrets(database_url=f"sqlite:///{tmp_path}/t.db", telegram_bot_token="x", telegram_chat_id="1", anthropic_api_key="")
    agent = orch.CryptoAgent(AgentConfig(), sec, md_factory=FakeMarketData)

    async def fake_send(text, preformatted_html=False):
        sent.append(text)
        return True

    agent.telegram.send = fake_send
    agent.cfg.alerts.min_abs_score = 20
    return agent


def test_full_scan_persists_and_alerts(tmp_path, monkeypatch):
    sent: list[str] = []
    agent = _agent(tmp_path, monkeypatch, sent)
    res = asyncio.run(agent.scan("full"))
    assert {a.symbol for a in res} == {"BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"}
    assert all(a.positioning is not None for a in res)
    assert agent.breadth.get("n") == 4
    with agent.db.session() as s:
        rows = list(s.scalars(select(Signal)))
    assert len(rows) == 4 and all(r.details and "timeframes" in r.details for r in rows)
    assert sent, "debería alertar al menos una señal"
    assert "No es asesoramiento financiero" in sent[0]

    # cooldown: el mismo escaneo no vuelve a alertar lo mismo
    n = len(sent)
    asyncio.run(agent.scan("full"))
    assert len(sent) == n

    # escaneo rápido sólo con 1h/15m
    fast = asyncio.run(agent.scan("fast"))
    assert all(set(a.timeframes) <= {"1h", "15m"} for a in fast)


def test_daily_report_template(tmp_path, monkeypatch):
    sent: list[str] = []
    agent = _agent(tmp_path, monkeypatch, sent)
    text = asyncio.run(agent.daily_report())
    assert "Informe diario" in text and "Fear & Greed: 55" in text
    assert sent[-1] == text


def test_outcome_and_component_stats(tmp_path):
    idx = pd.date_range("2026-01-01", periods=5, freq="1h", tz="UTC")
    path = pd.DataFrame({"high": [101, 102, 106, 103, 104], "low": [99, 98, 100, 97, 99]}, index=idx)
    plan = {"direction": "long", "stop": 97.5, "targets": [105]}
    assert outcome_from_path(100, plan, path) == "target"
    assert outcome_from_path(100, {**plan, "stop": 98.5}, path) == "stop"

    db = Database(f"sqlite:///{tmp_path}/s.db")
    with db.session() as s:
        for i in range(60):
            x = (i % 10 - 5) / 5
            s.add(Signal(
                symbol="BTC/USDT", price=100, score=x * 50, label="X", confidence=0.5,
                components={"trend": x, "momentum": -x}, evaluated=True, ret_72h=x * 2,
                ts=dt.datetime.now(dt.timezone.utc),
            ))  # fmt: skip
        s.commit()
    stats = update_component_stats(db)
    assert stats["trend"]["ic"] > 0.9 and stats["trend"]["weight_mult"] > 1
    assert stats["momentum"]["ic"] < -0.9 and stats["momentum"]["weight_mult"] == 0.5
    assert db.adaptive_weights()["trend"] == 1.5
    perf = performance_summary(db)
    assert perf["n"] > 0 and 0 <= perf["hit_rate_72h"] <= 1
    with db.session() as s:
        assert s.get(ComponentStat, "trend").n == 60


def test_backup_and_prune(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/b.db")
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=40)
    with db.session() as s:
        common = dict(symbol="BTC/USDT", price=1, score=1, label="X", confidence=1, components={}, details={"a": 1})
        s.add_all([Signal(kind="fast", ts=old, **common), Signal(kind="full", ts=old, **common), Signal(kind="full", **common)])
        s.commit()
    db.prune(30)
    with db.session() as s:
        rows = list(s.scalars(select(Signal)))
    assert len(rows) == 2 and sum(r.details is None for r in rows) == 1
    path = db.backup(str(tmp_path / "bk"))
    assert path and path.endswith(".db")


def test_telegram_chunks():
    text = "\n".join(f"línea {i} " + "x" * 90 for i in range(200))
    parts = _chunks(text)
    assert all(len(p) <= 4000 for p in parts)
    assert "".join(parts) == text
