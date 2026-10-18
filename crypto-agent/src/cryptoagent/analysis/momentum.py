"""Parámetros de momentum: RSI, MACD, StochRSI, ROC, MFI y divergencias."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .structure import find_swings


@dataclass
class MomentumResult:
    score: float
    rsi: float
    macd_hist: float
    stochrsi_k: float
    roc10: float
    divergences: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def detect_divergences(df: pd.DataFrame, osc: str = "rsi", max_age: int = 15) -> list[str]:
    """Divergencias regulares (reversión) y ocultas (continuación) entre precio y oscilador.

    Sólo se reportan si el último pivot tiene como mucho `max_age` velas.
    """
    out: list[str] = []
    n = len(df)
    highs, lows = find_swings(df["high"].to_numpy(), df["low"].to_numpy(), 3, 3)
    o = df[osc].to_numpy()

    if len(lows) >= 2 and n - 1 - lows[-1] <= max_age:
        a, b = lows[-2], lows[-1]
        pa, pb = df["low"].iloc[a], df["low"].iloc[b]
        if not (np.isnan(o[a]) or np.isnan(o[b])):
            if pb < pa and o[b] > o[a]:
                out.append(f"divergencia_alcista_regular_{osc}")
            elif pb > pa and o[b] < o[a]:
                out.append(f"divergencia_alcista_oculta_{osc}")
    if len(highs) >= 2 and n - 1 - highs[-1] <= max_age:
        a, b = highs[-2], highs[-1]
        pa, pb = df["high"].iloc[a], df["high"].iloc[b]
        if not (np.isnan(o[a]) or np.isnan(o[b])):
            if pb > pa and o[b] < o[a]:
                out.append(f"divergencia_bajista_regular_{osc}")
            elif pb < pa and o[b] > o[a]:
                out.append(f"divergencia_bajista_oculta_{osc}")
    return out


def analyze_momentum(df: pd.DataFrame, regime: str = "lateral") -> MomentumResult:
    last, prev = df.iloc[-1], df.iloc[-2]
    rsi, hist, k, d, roc = last["rsi"], last["macd_hist"], last["stochrsi_k"], last["stochrsi_d"], last["roc10"]
    notes: list[str] = []
    parts: list[float] = []

    # RSI: en tendencia, >50 confirma fuerza; en rango, los extremos son reversión
    if regime.startswith("tendencia"):
        parts.append(np.clip((rsi - 50) / 20, -1, 1))
    else:
        if rsi < 30:
            parts.append(0.8)
            notes.append("RSI en sobreventa")
        elif rsi > 70:
            parts.append(-0.8)
            notes.append("RSI en sobrecompra")
        else:
            parts.append(np.clip((rsi - 50) / 40, -0.5, 0.5))

    # MACD: signo y aceleración del histograma
    hist_slope = hist - prev["macd_hist"]
    parts.append(0.6 * np.sign(hist) + 0.4 * np.sign(hist_slope))
    if np.sign(hist) != np.sign(prev["macd_hist"]):
        notes.append("cruce MACD " + ("alcista" if hist > 0 else "bajista"))

    # StochRSI: cruces en zonas extremas (timing fino)
    if k > d and prev["stochrsi_k"] <= prev["stochrsi_d"] and k < 25:
        parts.append(0.8)
        notes.append("StochRSI cruce alcista en sobreventa")
    elif k < d and prev["stochrsi_k"] >= prev["stochrsi_d"] and k > 75:
        parts.append(-0.8)
        notes.append("StochRSI cruce bajista en sobrecompra")
    else:
        parts.append(np.clip((k - 50) / 100, -0.3, 0.3))

    # ROC normalizado por volatilidad (un 5% en BTC no es lo mismo que en una memecoin)
    atr_pct = max(float(last.get("atr_pct", 1.0)), 1e-6)
    parts.append(np.clip(roc / (3 * atr_pct), -1, 1))

    # MFI: momentum ponderado por volumen
    mfi = last["mfi"]
    parts.append(np.clip((mfi - 50) / 40, -1, 1))

    score = float(np.nanmean(parts))
    # La divergencia del histograma MACD es ruidosa sola: sólo confirma las del RSI
    macd_kinds = {d.removesuffix("_macd_hist") for d in detect_divergences(df, "macd_hist")}
    divs = []
    for dv in detect_divergences(df, "rsi"):
        kind = dv.removesuffix("_rsi")
        confirmed = kind in macd_kinds
        w = (0.35 if "regular" in kind else 0.2) * (1.3 if confirmed else 1.0)
        score += w if "alcista" in kind else -w
        divs.append(kind + ("_confirmada_macd" if confirmed else ""))
    return MomentumResult(
        score=float(np.clip(score, -1, 1)),
        rsi=float(rsi),
        macd_hist=float(hist),
        stochrsi_k=float(k),
        roc10=float(roc),
        divergences=divs,
        notes=notes,
    )
