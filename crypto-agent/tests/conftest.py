import numpy as np
import pandas as pd
import pytest

from cryptoagent.analysis.positioning import DerivativesData

FREQ = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}


def make_ohlcv(n: int = 400, drift: float = 0.0, vol: float = 0.01, seed: int = 1, freq: str = "1h", start: float = 100.0):
    rng = np.random.default_rng(seed)
    rets = drift + vol * rng.standard_normal(n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start], close[:-1]])
    spread = np.abs(rng.standard_normal(n)) * vol * close * 0.6
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.uniform(800, 1200, n) * (1 + 3 * np.abs(rets))
    up = close > open_
    taker = volume * np.where(up, rng.uniform(0.52, 0.65, n), rng.uniform(0.35, 0.48, n))
    idx = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume, "taker_buy_volume": taker}, index=idx
    )


def make_derivs(perp: pd.DataFrame, oi_trend: float = 0.002, funding_last: float = 0.0001, seed: int = 3) -> DerivativesData:
    rng = np.random.default_rng(seed)
    n = len(perp)
    oi = pd.Series(1e9 * np.exp(np.cumsum(oi_trend + 0.003 * rng.standard_normal(n))), index=perp.index)
    f_idx = pd.date_range(end=perp.index[-1], periods=120, freq="8h", tz="UTC")
    funding = pd.Series(0.0001 + 0.00003 * rng.standard_normal(120), index=f_idx)
    funding.iloc[-1] = funding_last
    top = pd.Series(1.2 + 0.05 * rng.standard_normal(n), index=perp.index)
    glob = pd.Series(1.0 + 0.05 * rng.standard_normal(n), index=perp.index)
    return DerivativesData(perp=perp, open_interest=oi, funding=funding, premium_pct=0.02, top_ls_ratio=top, global_ls_ratio=glob, spot=perp.copy())


@pytest.fixture
def uptrend():
    return make_ohlcv(drift=0.004, vol=0.008, seed=11)


@pytest.fixture
def downtrend():
    return make_ohlcv(drift=-0.004, vol=0.008, seed=12)


class FakeMarketData:
    """Sustituto de MarketData: datos sintéticos, sin red."""

    def __init__(self, cfg):
        self.cfg = cfg

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def universe(self):
        return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]

    async def candles(self, symbol, timeframe, limit, market="spot"):
        drift = {"BTC/USDT": 0.003, "ETH/USDT": 0.004, "SOL/USDT": -0.004, "DOGE/USDT": 0.0}[symbol]
        seed = sum(map(ord, symbol + timeframe))
        return make_ohlcv(min(limit, 400), drift=drift, vol=0.01, seed=seed, freq=FREQ[timeframe])
