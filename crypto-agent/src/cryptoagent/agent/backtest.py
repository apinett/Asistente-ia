"""Backtest walk-forward de los componentes técnicos (sin LPF: Binance sólo guarda 30 días de OI).

Para cada vela t se analiza la ventana [t-300, t] (sin mirar el futuro) y se mide el
retorno a `horizon` velas. Se reporta por componente:
  - IC: correlación de Spearman entre el score y el retorno futuro,
  - hit rate: % de veces que el signo del score acertó la dirección (|score| > 0.2),
  - retorno medio cuando el score es fuertemente positivo / negativo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..analysis.indicators import compute_indicators
from ..analysis.scoring import analyze_timeframe, combine

WINDOW = 300


def run_backtest(df: pd.DataFrame, timeframe: str, weights: dict[str, float], horizon: int = 12, step: int = 3) -> pd.DataFrame:
    ind = compute_indicators(df)
    close = ind["close"].to_numpy()
    rows = []
    for t in range(250, len(ind) - horizon, step):
        win = ind.iloc[max(0, t - WINDOW + 1) : t + 1]
        a = analyze_timeframe(win, timeframe)
        comb = combine("BT", {timeframe: a}, {timeframe: 1.0}, weights, timeframe)
        rows.append({**a.components(), "score_total": comb.score / 100, "fwd_ret": close[t + horizon] / close[t] - 1})
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    out = []
    for col in [c for c in results.columns if c != "fwd_ret"]:
        x, y = results[col], results["fwd_ret"]
        strong = results[x.abs() > 0.2]
        out.append(
            {
                "componente": col,
                "IC": round(float(x.corr(y, method="spearman")), 4),
                "hit_rate": round(float((np.sign(strong[col]) == np.sign(strong["fwd_ret"])).mean()), 3) if len(strong) else None,
                "ret_medio_score>0.3_%": round(float(y[x > 0.3].mean() * 100), 3) if (x > 0.3).any() else None,
                "ret_medio_score<-0.3_%": round(float(y[x < -0.3].mean() * 100), 3) if (x < -0.3).any() else None,
                "n": int(x.notna().sum()),
            }
        )
    return pd.DataFrame(out)
