"""Estructura de mercado: pivots, soportes/resistencias, BOS/CHoCH y Fair Value Gaps.

Lógica inspirada en joshyattridge/smart-money-concepts (MIT), reimplementada en
~150 líneas para no arrastrar sus dependencias (numba, pins de pandas) ni su
detección con look-ahead: acá un pivot sólo existe cuando ya cerraron `right` velas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Level:
    price: float
    touches: int
    kind: str  # "support" | "resistance"


@dataclass
class StructureResult:
    trend: str  # "alcista" | "bajista" | "lateral"
    last_event: str | None  # "BOS_alcista", "CHoCH_bajista", ...
    supports: list[Level] = field(default_factory=list)
    resistances: list[Level] = field(default_factory=list)
    bullish_fvg: list[tuple[float, float]] = field(default_factory=list)
    bearish_fvg: list[tuple[float, float]] = field(default_factory=list)
    score: float = 0.0


def find_swings(high: np.ndarray, low: np.ndarray, left: int = 3, right: int = 3):
    """Índices de pivots confirmados (máximo/mínimo local con `left`/`right` velas a cada lado)."""
    n = len(high)
    highs, lows = [], []
    for i in range(left, n - right):
        win_h = high[i - left : i + right + 1]
        win_l = low[i - left : i + right + 1]
        if high[i] == win_h.max() and np.argmax(win_h) == left:
            highs.append(i)
        if low[i] == win_l.min() and np.argmin(win_l) == left:
            lows.append(i)
    return np.array(highs, dtype=int), np.array(lows, dtype=int)


def _cluster_levels(prices: list[float], tol: float) -> list[tuple[float, int]]:
    if not prices:
        return []
    prices = sorted(prices)
    clusters: list[list[float]] = [[prices[0]]]
    for p in prices[1:]:
        if p - np.mean(clusters[-1]) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [(float(np.mean(c)), len(c)) for c in clusters]


def support_resistance(df: pd.DataFrame, highs: np.ndarray, lows: np.ndarray, atr: float, max_levels: int = 3):
    close = float(df["close"].iloc[-1])
    pivots = [float(df["high"].iloc[i]) for i in highs] + [float(df["low"].iloc[i]) for i in lows]
    levels = _cluster_levels(pivots, tol=0.5 * atr if atr > 0 else close * 0.005)
    sup = sorted((Level(p, t, "support") for p, t in levels if p < close), key=lambda x: close - x.price)
    res = sorted((Level(p, t, "resistance") for p, t in levels if p > close), key=lambda x: x.price - close)
    return sup[:max_levels], res[:max_levels]


def market_structure(df: pd.DataFrame, highs: np.ndarray, lows: np.ndarray) -> tuple[str, str | None]:
    """Tendencia por secuencia de pivots (HH/HL vs LH/LL) y último quiebre de estructura."""
    if len(highs) < 2 or len(lows) < 2:
        return "lateral", None
    h1, h2 = df["high"].iloc[highs[-2]], df["high"].iloc[highs[-1]]
    l1, l2 = df["low"].iloc[lows[-2]], df["low"].iloc[lows[-1]]
    if h2 > h1 and l2 > l1:
        trend = "alcista"
    elif h2 < h1 and l2 < l1:
        trend = "bajista"
    else:
        trend = "lateral"

    last_high = float(df["high"].iloc[highs[-1]])
    last_low = float(df["low"].iloc[lows[-1]])
    after = df.iloc[max(highs[-1], lows[-1]) + 1 :]
    event = None
    if len(after):
        if (after["close"] > last_high).any():
            event = "BOS_alcista" if trend != "bajista" else "CHoCH_alcista"
        elif (after["close"] < last_low).any():
            event = "BOS_bajista" if trend != "alcista" else "CHoCH_bajista"
    return trend, event


def fair_value_gaps(df: pd.DataFrame, lookback: int = 50):
    """FVG de 3 velas aún no rellenados en las últimas `lookback` velas."""
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    n = len(df)
    bull, bear = [], []
    for i in range(max(2, n - lookback), n):
        if l[i] > h[i - 2]:  # hueco alcista entre high[i-2] y low[i]
            bottom, top = h[i - 2], l[i]
            if i + 1 >= n or l[i + 1 :].min() > bottom:
                bull.append((float(bottom), float(top)))
        if h[i] < l[i - 2]:  # hueco bajista
            bottom, top = h[i], l[i - 2]
            if i + 1 >= n or h[i + 1 :].max() < top:
                bear.append((float(bottom), float(top)))
    return bull[-3:], bear[-3:]


def analyze_structure(df: pd.DataFrame) -> StructureResult:
    highs, lows = find_swings(df["high"].to_numpy(), df["low"].to_numpy())
    atr = float(df["atr"].iloc[-1]) if "atr" in df and not np.isnan(df["atr"].iloc[-1]) else 0.0
    sup, res = support_resistance(df, highs, lows, atr)
    trend, event = market_structure(df, highs, lows)
    bull_fvg, bear_fvg = fair_value_gaps(df)

    score = {"alcista": 0.5, "bajista": -0.5, "lateral": 0.0}[trend]
    if event:
        score += 0.5 if event.endswith("alcista") else -0.5
    # Proximidad a niveles: cerca de soporte fuerte favorece rebote, cerca de resistencia lo limita
    close = float(df["close"].iloc[-1])
    if atr > 0:
        if sup and (close - sup[0].price) < atr and sup[0].touches >= 2:
            score += 0.2
        if res and (res[0].price - close) < atr and res[0].touches >= 2:
            score -= 0.2
    return StructureResult(
        trend=trend,
        last_event=event,
        supports=sup,
        resistances=res,
        bullish_fvg=bull_fvg,
        bearish_fvg=bear_fvg,
        score=float(np.clip(score, -1, 1)),
    )
