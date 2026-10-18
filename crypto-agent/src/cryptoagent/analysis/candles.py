"""Patrones de velas japonesas (61 detectores de TA-Lib) con filtro de contexto.

Un patrón aislado tiene poco poder predictivo. Por eso cada detección se pondera por:
  - fiabilidad histórica del patrón (tabla RELIABILITY),
  - contexto de tendencia previa (un martillo sólo importa tras una caída),
  - ubicación (cerca de soporte/resistencia, medido en ATR),
  - volumen relativo (confirmación de participación),
  - confirmación posterior (la vela siguiente cierra a favor).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import talib

PATTERNS: list[str] = talib.get_function_groups()["Pattern Recognition"]

# Patrones de indecisión: TA-Lib devuelve +100 sin dirección real
INDECISION = {"CDLDOJI", "CDLSPINNINGTOP", "CDLHIGHWAVE", "CDLLONGLEGGEDDOJI", "CDLRICKSHAWMAN", "CDLDOJISTAR"}

# Fiabilidad relativa (0-1) según la literatura (Bulkowski) y uso práctico; resto = 0.4
RELIABILITY = {
    "CDLENGULFING": 0.8,
    "CDLMORNINGSTAR": 0.85,
    "CDLEVENINGSTAR": 0.85,
    "CDLMORNINGDOJISTAR": 0.8,
    "CDLEVENINGDOJISTAR": 0.8,
    "CDL3WHITESOLDIERS": 0.8,
    "CDL3BLACKCROWS": 0.8,
    "CDL3INSIDE": 0.7,
    "CDL3OUTSIDE": 0.75,
    "CDLHAMMER": 0.65,
    "CDLHANGINGMAN": 0.55,
    "CDLINVERTEDHAMMER": 0.55,
    "CDLSHOOTINGSTAR": 0.65,
    "CDLPIERCING": 0.7,
    "CDLDARKCLOUDCOVER": 0.7,
    "CDLHARAMI": 0.5,
    "CDLHARAMICROSS": 0.5,
    "CDLMARUBOZU": 0.6,
    "CDLABANDONEDBABY": 0.85,
    "CDLKICKING": 0.75,
    "CDLRISEFALL3METHODS": 0.7,
    "CDLDRAGONFLYDOJI": 0.55,
    "CDLGRAVESTONEDOJI": 0.55,
    "CDLBELTHOLD": 0.5,
    "CDLHIKKAKE": 0.5,
    "CDLTASUKIGAP": 0.55,
}

NAMES_ES = {
    "CDLENGULFING": "envolvente",
    "CDLMORNINGSTAR": "estrella de la mañana",
    "CDLEVENINGSTAR": "estrella del atardecer",
    "CDL3WHITESOLDIERS": "tres soldados blancos",
    "CDL3BLACKCROWS": "tres cuervos negros",
    "CDLHAMMER": "martillo",
    "CDLHANGINGMAN": "hombre colgado",
    "CDLINVERTEDHAMMER": "martillo invertido",
    "CDLSHOOTINGSTAR": "estrella fugaz",
    "CDLPIERCING": "pauta penetrante",
    "CDLDARKCLOUDCOVER": "nube oscura",
    "CDLHARAMI": "harami",
    "CDLDOJI": "doji",
    "CDLMARUBOZU": "marubozu",
}


@dataclass
class PatternHit:
    name: str
    bars_ago: int
    direction: int  # +1 alcista / -1 bajista / 0 indecisión
    weight: float  # 0-1 tras contexto
    context: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        base = NAMES_ES.get(self.name, self.name.removeprefix("CDL").lower())
        side = {1: "alcista", -1: "bajista", 0: "indecisión"}[self.direction]
        return f"{base} {side}"


@dataclass
class CandleResult:
    score: float
    hits: list[PatternHit]


def _prior_trend(close: np.ndarray, i: int, n: int = 5) -> float:
    if i - n < 0:
        return 0.0
    return (close[i] / close[i - n]) - 1


def analyze_candles(
    df: pd.DataFrame,
    supports: list[float] | None = None,
    resistances: list[float] | None = None,
    lookback: int = 3,
) -> CandleResult:
    o, h, l, c = (df[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close"))
    atr = df["atr"].to_numpy() if "atr" in df else np.full(len(df), np.nan)
    relvol = df["rel_volume"].to_numpy() if "rel_volume" in df else np.ones(len(df))
    supports = supports or []
    resistances = resistances or []
    n = len(df)
    hits: list[PatternHit] = []

    for name in PATTERNS:
        res = getattr(talib, name)(o, h, l, c)
        for ago in range(lookback):
            i = n - 1 - ago
            val = res[i]
            if val == 0:
                continue
            direction = 0 if name in INDECISION else int(np.sign(val))
            w = RELIABILITY.get(name, 0.4) * (1.0 if abs(val) < 200 else 1.15)  # ±200 = patrón confirmado
            ctx: list[str] = []
            trend = _prior_trend(c, i)
            a = atr[i] if not np.isnan(atr[i]) else c[i] * 0.01

            if direction == 1:
                if trend < 0:
                    w *= 1.3
                    ctx.append("tras caída")
                else:
                    w *= 0.6
                if any(abs(l[i] - s) <= a for s in supports):
                    w *= 1.4
                    ctx.append("en soporte")
            elif direction == -1:
                if trend > 0:
                    w *= 1.3
                    ctx.append("tras subida")
                else:
                    w *= 0.6
                if any(abs(h[i] - r) <= a for r in resistances):
                    w *= 1.4
                    ctx.append("en resistencia")
            if relvol[i] > 1.3:
                w *= 1.2
                ctx.append(f"volumen x{relvol[i]:.1f}")
            if ago > 0 and direction != 0:
                confirmed = c[-1] > h[i] if direction == 1 else c[-1] < l[i]
                failed = c[-1] < l[i] if direction == 1 else c[-1] > h[i]
                if confirmed:
                    w *= 1.3
                    ctx.append("confirmado")
                elif failed:
                    w *= 0.2
                    ctx.append("invalidado")
            w *= 1.0 - 0.2 * ago  # decaimiento temporal
            hits.append(PatternHit(name, ago, direction, float(min(w, 1.0)), ctx))

    directional = [x.direction * x.weight for x in hits if x.direction != 0]
    score = float(np.clip(np.sum(directional) / 1.5, -1, 1)) if directional else 0.0
    hits.sort(key=lambda x: (-abs(x.direction * x.weight), x.bars_ago))
    return CandleResult(score=score, hits=hits[:6])
