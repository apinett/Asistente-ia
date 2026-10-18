"""Indicadores técnicos sobre TA-Lib (implementación en C, rápida y probada).

Todos los indicadores son causales: el valor en la vela t sólo usa datos hasta t,
por lo que el mismo DataFrame sirve para análisis en vivo y para backtesting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import talib

OHLCV = ["open", "high", "low", "close", "volume"]


def _arr(df: pd.DataFrame, col: str) -> np.ndarray:
    return df[col].to_numpy(dtype=np.float64)


def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 10, mult: float = 3.0):
    """Supertrend clásico. Devuelve (línea, dirección) con dirección +1 alcista / -1 bajista."""
    atr = talib.ATR(high, low, close, period)
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    n = len(close)
    line = np.full(n, np.nan)
    direction = np.zeros(n)
    start = int(np.argmax(~np.isnan(atr)))
    if np.isnan(atr[start]):
        return line, direction
    fu, fl = upper[start], lower[start]
    d = 1
    for i in range(start, n):
        if i > start:
            fu = upper[i] if (upper[i] < fu or close[i - 1] > fu) else fu
            fl = lower[i] if (lower[i] > fl or close[i - 1] < fl) else fl
            if d == 1 and close[i] < fl:
                d = -1
            elif d == -1 and close[i] > fu:
                d = 1
        direction[i] = d
        line[i] = fl if d == 1 else fu
    return line, direction


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas de tendencia, momentum, volatilidad y volumen al OHLCV."""
    o, h, l, c, v = (_arr(df, k) for k in OHLCV)
    out = df.copy()

    # --- Tendencia ---
    out["ema20"] = talib.EMA(c, 20)
    out["ema50"] = talib.EMA(c, 50)
    out["ema200"] = talib.EMA(c, 200)
    out["adx"] = talib.ADX(h, l, c, 14)
    out["plus_di"] = talib.PLUS_DI(h, l, c, 14)
    out["minus_di"] = talib.MINUS_DI(h, l, c, 14)
    st_line, st_dir = supertrend(h, l, c)
    out["supertrend"] = st_line
    out["supertrend_dir"] = st_dir

    # --- Momentum ---
    out["rsi"] = talib.RSI(c, 14)
    macd, macd_sig, macd_hist = talib.MACD(c, 12, 26, 9)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd, macd_sig, macd_hist
    k, d = talib.STOCHRSI(c, 14, 3, 3)
    out["stochrsi_k"], out["stochrsi_d"] = k, d
    out["roc10"] = talib.ROC(c, 10)
    out["mfi"] = talib.MFI(h, l, c, v, 14)

    # --- Volatilidad ---
    out["atr"] = talib.ATR(h, l, c, 14)
    out["atr_pct"] = out["atr"] / out["close"] * 100
    bb_u, bb_m, bb_l = talib.BBANDS(c, 20, 2.0, 2.0)
    out["bb_upper"], out["bb_mid"], out["bb_lower"] = bb_u, bb_m, bb_l
    out["bb_width"] = (bb_u - bb_l) / bb_m
    atr20 = talib.ATR(h, l, c, 20)
    out["kc_upper"] = out["ema20"] + 1.5 * atr20
    out["kc_lower"] = out["ema20"] - 1.5 * atr20
    # TTM squeeze: Bollinger dentro de Keltner = compresión de volatilidad (precede expansiones)
    out["squeeze"] = (out["bb_upper"] < out["kc_upper"]) & (out["bb_lower"] > out["kc_lower"])

    # --- Volumen ---
    out["obv"] = talib.OBV(c, v)
    rng = np.where(h - l == 0, np.nan, h - l)
    mfm = ((c - l) - (h - c)) / rng
    mfv = pd.Series(np.nan_to_num(mfm) * v, index=df.index)
    out["cmf"] = mfv.rolling(20).sum() / df["volume"].rolling(20).sum()
    out["rel_volume"] = df["volume"] / df["volume"].rolling(20).mean()
    return out
