import numpy as np
import pandas as pd

from cryptoagent.analysis.positioning import (
    PositioningResult,
    analyze_positioning,
    estimate_liquidations,
    momentum_quality,
    oi_price_quadrant,
)

from .conftest import make_derivs, make_ohlcv


def _series(vals):
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=len(vals), freq="1h", tz="UTC"))


def test_quadrants():
    up, down = _series(np.linspace(100, 105, 30)), _series(np.linspace(105, 100, 30))
    oi_up, oi_dn = _series(np.linspace(1e9, 1.05e9, 30)), _series(np.linspace(1.05e9, 1e9, 30))
    assert oi_price_quadrant(up, oi_up, 24)[0] == "nuevos_largos"
    assert oi_price_quadrant(up, oi_dn, 24)[0] == "cierre_de_cortos"
    assert oi_price_quadrant(down, oi_up, 24)[0] == "nuevos_cortos"
    assert oi_price_quadrant(down, oi_dn, 24)[0] == "liquidacion_de_largos"
    assert oi_price_quadrant(up, oi_up, 24)[3] > 0 > oi_price_quadrant(down, oi_up, 24)[3]


def test_liquidation_map_sides_and_sweeps():
    perp = make_ohlcv(200, drift=0.0, vol=0.004, seed=4)
    oi = pd.Series(np.linspace(1e9, 1.3e9, 200), index=perp.index)
    above, below, imb = estimate_liquidations(perp, oi, {10: 0.5, 25: 0.5})
    price = perp["close"].iloc[-1]
    assert all(c.price > price and c.side == "shorts" for c in above)
    assert all(c.price < price and c.side == "longs" for c in below)
    assert imb is None or -1 <= imb <= 1
    # ningún nivel listado puede haber sido atravesado ya por el precio posterior
    for c in below:
        assert c.price < perp["low"].iloc[-1] * 1.0001 or c.distance_pct < 0


def test_short_squeeze_detection():
    perp = make_ohlcv(300, drift=0.0005, vol=0.003, seed=8)
    d = make_derivs(perp, oi_trend=0.003, funding_last=-0.0004)
    res = analyze_positioning(d, lookback=24)
    assert res.funding_z < -1
    assert res.squeeze_risk == "short_squeeze"
    assert res.components["squeeze"] > 0
    assert -1 <= res.score <= 1


def test_degrades_without_optional_data():
    perp = make_ohlcv(100, seed=2).drop(columns=["taker_buy_volume"])
    from cryptoagent.analysis.positioning import DerivativesData

    res = analyze_positioning(DerivativesData(perp=perp), lookback=24)
    assert res.score == 0.0 and res.components == {}
    assert res.momentum_quality == 1.0


def test_momentum_quality_bounds():
    good = PositioningResult(score=0, momentum_quality=1, quadrant="nuevos_largos", flow_leader="spot (suba sana)")
    bad = PositioningResult(score=0, momentum_quality=1, quadrant="cierre_de_cortos", flow_leader="perpetuos (suba frágil, apalancada)", squeeze_risk="long_squeeze")
    assert momentum_quality(good, 1) > 1.0
    assert 0.6 <= momentum_quality(bad, 1) < 1.0
    assert momentum_quality(good, 0) == 1.0


def test_quadrant_with_misaligned_oi_timestamps():
    price = _series(np.linspace(100, 105, 30))
    oi = pd.Series(np.linspace(1e9, 1.05e9, 30), index=price.index + pd.Timedelta(seconds=-1))
    assert oi_price_quadrant(price, oi, 24)[0] == "nuevos_largos"
