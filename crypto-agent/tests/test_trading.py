import asyncio
import datetime as dt

import pytest
from sqlalchemy import select

from cryptoagent.agent.stats import effectiveness, r_multiple
from cryptoagent.analysis.scoring import SymbolAnalysis, TradePlan
from cryptoagent.config import AgentConfig, Secrets
from cryptoagent.storage.db import ComponentStat, Database, Signal, Trade
from cryptoagent.trading.engine import TradingEngine
from cryptoagent.trading.readiness import compute_readiness


class Prices:
    def __init__(self, **px):
        self.px = {k.replace("_", "/"): v for k, v in px.items()}

    async def __call__(self, symbols):
        return {s: self.px[s] for s in symbols if s in self.px}


def _analysis(symbol="BTC/USDT", price=100.0, score=70, conf=0.8, stop=95.0, target=110.0):
    plan = TradePlan("long", price * 0.99, price, stop, [target], (target - price) / (price - stop), "")
    return SymbolAnalysis(symbol, price, score, "ALCISTA FUERTE", conf, {}, {}, plan=plan)


@pytest.fixture
def engine(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/t.db")
    sent: list[str] = []

    async def notify(text):
        sent.append(text)

    eng = TradingEngine(AgentConfig(), Secrets(), db, Prices(BTC_USDT=100.0, ETH_USDT=50.0), notify=notify)
    eng.sent = sent
    return eng


def run(coro):
    return asyncio.run(coro)


def test_paused_by_default_never_trades(engine):
    assert engine.desired_mode() == "paused" and engine.effective_mode() == "paused"
    assert run(engine.on_scan([_analysis()])) == []
    with engine.db.session() as s:
        assert s.scalar(select(Trade)) is None


def test_live_blocked_without_gates(engine):
    ok, msg = run(engine.set_mode("live"))
    assert not ok and "TRADING_LIVE_ENABLED" in msg and "API key" in msg
    assert engine.desired_mode() == "paused"


def test_live_requested_but_gate_lost_falls_back_to_paused(engine):
    engine.db.set_kv("trading_mode", "live")  # p. ej. se quitaron las keys después de activarlo
    assert engine.effective_mode() == "paused"
    assert run(engine.on_scan([_analysis()])) == []


def test_paper_open_size_and_close_on_target(engine):
    ok, _ = run(engine.set_mode("paper"))
    assert ok
    opened = run(engine.on_scan([_analysis(), _analysis("ETH/USDT", 50, score=40)]))  # ETH no califica (score)
    assert [t.symbol for t in opened] == ["BTC/USDT"]
    tr = opened[0]
    # riesgo 1% de 10.000 = 100 USDT; tope 10% = 1.000 USDT de posición → manda el tope
    assert tr.qty * tr.entry_price <= 1000 * 1.001  # tope + slippage simulado del 0.05%
    assert tr.risk_usd == pytest.approx((tr.entry_price - 95) * tr.qty)
    # no duplica posición en el mismo activo
    assert run(engine.on_scan([_analysis()])) == []

    engine.prices.px["BTC/USDT"] = 111.0
    run(engine.monitor())
    with engine.db.session() as s:
        closed = s.scalar(select(Trade))
    assert closed.status == "closed" and closed.exit_reason == "objetivo"
    assert closed.pnl_usd > 0 and closed.r_multiple > 0
    acc = engine.account("paper")
    assert acc["closed_trades"] == 1 and acc["equity"] > 10_000
    assert any("COMPRA BTC/USDT" in m for m in engine.sent) and any("VENTA BTC/USDT" in m for m in engine.sent)


def test_stop_and_contrary_signal_exits(engine):
    run(engine.set_mode("paper"))
    run(engine.on_scan([_analysis(), _analysis("ETH/USDT", 50, stop=47, target=56)]))
    engine.prices.px["BTC/USDT"] = 94.0
    run(engine.monitor())
    bearish = _analysis("ETH/USDT", 50, score=-40)
    run(engine.on_scan([bearish]))
    trades = {t["symbol"]: t for t in engine.trades()}
    assert trades["BTC/USDT"]["exit_reason"] == "stop" and trades["BTC/USDT"]["r"] < 0
    assert trades["ETH/USDT"]["exit_reason"] == "señal_contraria"


def test_kill_switch_pauses_and_closes(engine):
    engine.cfg.trading.max_position_pct = 50
    engine.cfg.trading.risk_per_trade_pct = 5
    run(engine.set_mode("paper"))
    run(engine.on_scan([_analysis(stop=60, target=200)]))
    engine.prices.px["BTC/USDT"] = 61.0  # -39% sin tocar el stop: pérdida diaria muy superior al 3%
    run(engine.monitor())
    assert engine.desired_mode() == "paused"
    assert "kill switch" in engine.db.get_kv("trading_mode_reason")["reason"]
    assert engine.account("paper")["open_positions"] == 0


def test_paper_kill_switch_never_touches_live_positions(engine):
    engine.cfg.trading.max_position_pct = 50
    engine.cfg.trading.risk_per_trade_pct = 5
    with engine.db.session() as s:  # posición real abierta antes (p. ej. de cuando estaba en modo real)
        s.add(Trade(mode="live", symbol="ETH/USDT", entry_price=50, qty=1, stop=40, target=70, risk_usd=10,
                    signal_score=70, signal_confidence=0.8))  # fmt: skip
        s.commit()
    run(engine.set_mode("paper"))
    run(engine.on_scan([_analysis(stop=60, target=200)]))
    engine.prices.px["BTC/USDT"] = 61.0
    run(engine.monitor())
    assert engine.desired_mode() == "paused"
    assert engine.account("paper")["open_positions"] == 0
    assert engine.account("live")["open_positions"] == 1


def test_max_open_positions(engine):
    engine.cfg.trading.max_open_positions = 2
    run(engine.set_mode("paper"))
    syms = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    engine.prices.px["SOL/USDT"] = 100.0
    opened = run(engine.on_scan([_analysis(s) for s in syms]))
    assert len(opened) == 2


def _seed_signals(db: Database, n: int, hit: bool, days_ago: float = 30):
    ts = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)
    plan = {"direction": "long", "stop": 95, "targets": [110], "risk_reward": 2.0}
    with db.session() as s:
        for i in range(n):
            s.add(Signal(
                kind="full", symbol="BTC/USDT", price=100, score=70, label="ALCISTA FUERTE", confidence=0.8,
                components={"trend": 0.5}, plan=plan, evaluated=True, ret_24h=1.0 if hit else -1.0,
                ret_72h=3.0 if hit else -2.0, outcome="target" if hit else "stop",
                ts=ts + dt.timedelta(hours=i),
            ))  # fmt: skip
        s.commit()


def test_readiness_progresses_with_evidence(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/r.db")
    cfg = AgentConfig()
    empty = compute_readiness(db, cfg)
    assert empty["level_pct"] == 0 and not empty["ready_for_live"]

    _seed_signals(db, 240, True)
    _seed_signals(db, 120, False, days_ago=29)
    with db.session() as s:
        s.add(ComponentStat(name="score_total", ic=0.08, hit_rate=0.66, n=360, weight_mult=1.2))
        for i in range(25):
            pnl = 30.0 if i % 3 else -20.0
            s.add(Trade(mode="paper", symbol="BTC/USDT", status="closed", entry_price=100, qty=1, stop=95, target=110,
                        risk_usd=5, signal_score=70, signal_confidence=0.8, pnl_usd=pnl, r_multiple=pnl / 5,
                        exit_ts=dt.datetime.now(dt.timezone.utc)))  # fmt: skip
        s.commit()
    rd = compute_readiness(db, cfg)
    checks = {c["key"]: c for c in rd["checks"]}
    assert checks["hit_rate"]["ok"] and checks["hit_rate"]["value"] == pytest.approx(66.7, abs=0.1)
    assert checks["expectancy"]["ok"]  # (240·2 − 120) / 360 = 1.0 R
    assert checks["profit_factor"]["ok"]
    assert rd["ready_for_live"] and rd["level_pct"] == 100


def test_effectiveness_stats(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/e.db")
    _seed_signals(db, 30, True, days_ago=10)
    _seed_signals(db, 10, False, days_ago=5)
    st = effectiveness(db, days=30)
    assert st["summary"]["n"] == 40
    assert st["summary"]["hit_rate_72h"] == 0.75
    assert st["summary"]["targets"] == 30 and st["summary"]["stops"] == 10
    assert st["summary"]["expectancy_r"] == pytest.approx((30 * 2 - 10) / 40)
    assert st["daily"] and st["daily"][-1]["hit_rate_7d"] is not None
    assert {b["bucket"] for b in st["by_confidence"]} >= {"0.60–0.80"}
    fuerte = next(x for x in st["by_label"] if x["label"] == "ALCISTA FUERTE")
    assert fuerte["n"] == 40


def test_r_multiple():
    plan = {"direction": "long", "stop": 95, "targets": [110], "risk_reward": 2.0}
    assert r_multiple(100, plan, "target", 5) == 2.0
    assert r_multiple(100, plan, "stop", -5) == -1.0
    assert r_multiple(100, plan, "abierta", 2.5) == pytest.approx(0.5)
    assert r_multiple(100, None, "abierta", 2.5) is None
