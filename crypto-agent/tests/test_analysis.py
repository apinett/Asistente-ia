import numpy as np
import pandas as pd

from cryptoagent.analysis.candles import analyze_candles
from cryptoagent.analysis.indicators import compute_indicators
from cryptoagent.analysis.momentum import analyze_momentum
from cryptoagent.analysis.regime import hmm_market_regime, rule_regime
from cryptoagent.analysis.relative import market_breadth, relative_strength
from cryptoagent.analysis.structure import analyze_structure, fair_value_gaps, find_swings

from .conftest import make_ohlcv


def test_indicators_are_causal(uptrend):
    full = compute_indicators(uptrend)
    prefix = compute_indicators(uptrend.iloc[:300])
    for col in ("ema20", "rsi", "macd_hist", "atr", "adx", "supertrend_dir", "cmf"):
        assert np.isclose(full[col].iloc[299], prefix[col].iloc[-1], equal_nan=True), col


def test_trend_regimes(uptrend, downtrend):
    up = compute_indicators(uptrend)
    dn = compute_indicators(downtrend)
    assert rule_regime(up).name == "tendencia_alcista"
    assert rule_regime(dn).name == "tendencia_bajista"
    assert analyze_momentum(up, "tendencia_alcista").score > 0
    assert analyze_momentum(dn, "tendencia_bajista").score < 0


def test_swings_zigzag():
    x = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 3, 4], dtype=float)
    highs, lows = find_swings(x + 0.1, x - 0.1, 3, 3)
    assert 4 in highs and 13 in highs
    assert 8 in lows


def test_structure_levels(uptrend):
    df = compute_indicators(uptrend)
    st = analyze_structure(df)
    close = df["close"].iloc[-1]
    assert all(lv.price < close for lv in st.supports)
    assert all(lv.price > close for lv in st.resistances)
    assert st.trend in ("alcista", "bajista", "lateral")
    assert -1 <= st.score <= 1


def test_fair_value_gap():
    idx = pd.date_range("2026-01-01", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"open": [10, 10.5, 11, 13, 13.5], "high": [10.6, 11, 13.2, 13.8, 14], "low": [9.9, 10.4, 10.9, 12.8, 13.2], "close": [10.5, 11, 13, 13.5, 13.8]},
        index=idx,
    )
    bull, bear = fair_value_gaps(df)
    assert (10.6, 10.9) in bull and (11.0, 12.8) in bull
    assert not bear


def test_bullish_engulfing_in_context():
    df = make_ohlcv(120, drift=-0.004, vol=0.004, seed=5)
    # forzar una envolvente alcista en la última vela tras la caída
    o2, c2 = df["close"].iloc[-3], df["close"].iloc[-3] * 0.99
    df.iloc[-2, df.columns.get_loc("open")] = o2
    df.iloc[-2, df.columns.get_loc("close")] = c2
    df.iloc[-2, df.columns.get_loc("high")] = o2 * 1.001
    df.iloc[-2, df.columns.get_loc("low")] = c2 * 0.999
    df.iloc[-1, df.columns.get_loc("open")] = c2 * 0.998
    df.iloc[-1, df.columns.get_loc("close")] = o2 * 1.004
    df.iloc[-1, df.columns.get_loc("high")] = o2 * 1.005
    df.iloc[-1, df.columns.get_loc("low")] = c2 * 0.997
    df.iloc[-1, df.columns.get_loc("volume")] *= 3
    res = analyze_candles(compute_indicators(df))
    engulf = [h for h in res.hits if h.name == "CDLENGULFING" and h.bars_ago == 0]
    assert engulf and engulf[0].direction == 1
    assert "tras caída" in engulf[0].context
    assert res.score > 0


def test_relative_strength_and_breadth():
    a = make_ohlcv(200, drift=0.005, seed=1, freq="1D")
    b = make_ohlcv(200, drift=0.0, seed=2, freq="1D")
    assert relative_strength(a["close"], b["close"]) > 0
    assert relative_strength(b["close"], a["close"]) < 0
    br = market_breadth({"A": compute_indicators(a), "B": compute_indicators(b)})
    assert br["n"] == 2 and 0 <= br["pct_above_ema50"] <= 100


def test_hmm_regime_runs():
    df = make_ohlcv(600, drift=0.001, vol=0.03, seed=9, freq="1D")
    reg = hmm_market_regime(df)
    assert reg is not None and 0 <= reg.probability <= 1
