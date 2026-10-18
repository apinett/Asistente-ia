"""Estudio de mercado continuo: fuerza relativa contra BTC y amplitud (breadth) del mercado."""

from __future__ import annotations

import numpy as np
import pandas as pd


def relative_strength(sym_close: pd.Series, btc_close: pd.Series, window: int = 30) -> float:
    """Score [-1, 1] de la serie ratio activo/BTC: ¿el activo le gana a BTC?"""
    ratio = (sym_close / btc_close.reindex(sym_close.index)).dropna()
    if len(ratio) <= window:
        return 0.0
    roc = ratio.iloc[-1] / ratio.iloc[-window] - 1
    ema = ratio.ewm(span=20, adjust=False).mean()
    score = float(np.clip(roc * 5, -0.7, 0.7)) + (0.3 if ratio.iloc[-1] > ema.iloc[-1] else -0.3)
    return float(np.clip(score, -1, 1))


def market_breadth(daily: dict[str, pd.DataFrame]) -> dict:
    """Salud interna del mercado sobre el universo analizado (velas diarias con indicadores)."""
    rows = []
    for sym, df in daily.items():
        if len(df) < 8:
            continue
        last = df.iloc[-1]
        rows.append(
            {
                "symbol": sym,
                "above_ema50": bool(last["close"] > last.get("ema50", np.nan)),
                "above_ema200": bool(last["close"] > last.get("ema200", np.nan)),
                "ret_7d": float(last["close"] / df["close"].iloc[-8] - 1) * 100,
                "ret_1d": float(last["close"] / df["close"].iloc[-2] - 1) * 100,
            }
        )
    if not rows:
        return {}
    t = pd.DataFrame(rows)
    leaders = t.sort_values("ret_7d", ascending=False)
    return {
        "n": len(t),
        "pct_above_ema50": round(t["above_ema50"].mean() * 100, 1),
        "pct_above_ema200": round(t["above_ema200"].mean() * 100, 1),
        "avg_ret_7d": round(t["ret_7d"].mean(), 2),
        "advancers_1d": int((t["ret_1d"] > 0).sum()),
        "decliners_1d": int((t["ret_1d"] <= 0).sum()),
        "leaders_7d": leaders.head(5)[["symbol", "ret_7d"]].round(2).to_dict("records"),
        "laggards_7d": leaders.tail(5)[["symbol", "ret_7d"]].round(2).to_dict("records"),
    }
