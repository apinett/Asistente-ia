from cryptoagent.agent.backtest import run_backtest, summarize
from cryptoagent.analysis.indicators import compute_indicators
from cryptoagent.analysis.scoring import analyze_timeframe, combine
from cryptoagent.config import AgentConfig

from .conftest import make_ohlcv

W = AgentConfig().scoring.weights


def _analysis(df, tf="4h"):
    return analyze_timeframe(compute_indicators(df), tf)


def test_uptrend_scores_bullish_with_long_plan(uptrend):
    a = combine("X/USDT", {"4h": _analysis(uptrend)}, {"4h": 1.0}, W, "4h")
    assert a.score > 25 and a.label.startswith("ALCISTA")
    p = a.plan
    assert p and p.direction == "long"
    assert p.stop < a.price <= p.entry_high and p.targets[0] > a.price
    assert p.risk_reward > 0


def test_downtrend_scores_bearish_with_short_plan(downtrend):
    a = combine("X/USDT", {"4h": _analysis(downtrend)}, {"4h": 1.0}, W, "4h")
    assert a.score < -25 and a.label.startswith("BAJISTA")
    assert a.plan.direction == "short" and a.plan.stop > a.price > a.plan.targets[0]


def test_multi_timeframe_alignment(uptrend, downtrend):
    aligned = combine("X", {"1d": _analysis(uptrend, "1d"), "4h": _analysis(uptrend)}, {"1d": 0.5, "4h": 0.5}, W, "4h")
    mixed = combine("X", {"1d": _analysis(uptrend, "1d"), "4h": _analysis(downtrend)}, {"1d": 0.5, "4h": 0.5}, W, "4h")
    assert aligned.alignment == 1.0
    assert mixed.alignment < 1.0
    assert abs(mixed.score) < abs(aligned.score)


def test_adaptive_weights_change_score(uptrend):
    t = {"4h": _analysis(uptrend)}
    base = combine("X", t, {"4h": 1.0}, W, "4h")
    damp = combine("X", t, {"4h": 1.0}, W, "4h", adaptive={"trend": 0.5, "momentum": 0.5})
    assert base.score != damp.score


def test_backtest_summary():
    df = make_ohlcv(450, drift=0.001, vol=0.01, seed=21, freq="4h")
    res = run_backtest(df, "4h", W, horizon=6, step=10)
    summ = summarize(res)
    assert {"trend", "momentum", "score_total"} <= set(summ["componente"])
    assert len(res) > 10
