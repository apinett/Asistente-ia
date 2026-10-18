"""Detección de régimen de mercado.

Dos capas:
  1. Por activo y temporalidad: reglas (ADX, alineación de EMAs, percentil de volatilidad).
  2. Mercado global (sobre BTC diario): Hidden Markov Model de 3 estados sobre
     retorno y volatilidad (hmmlearn). Si el ajuste falla, se usa sólo la capa 1.

El régimen decide qué componentes pesan más: en tendencia manda el seguimiento de
tendencia; en rango, la reversión a la media y los patrones en niveles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class Regime:
    name: str  # tendencia_alcista | tendencia_bajista | lateral | alta_volatilidad
    adx: float
    vol_percentile: float


def rule_regime(df: pd.DataFrame) -> Regime:
    last = df.iloc[-1]
    adx = float(last["adx"]) if not np.isnan(last["adx"]) else 0.0
    atr_pct = df["atr_pct"].dropna()
    vol_pct = float((atr_pct.iloc[-200:] <= atr_pct.iloc[-1]).mean()) if len(atr_pct) else 0.5
    ema_up = last["close"] > last["ema20"] > last["ema50"]
    ema_dn = last["close"] < last["ema20"] < last["ema50"]

    if vol_pct > 0.95 and adx < 25:
        name = "alta_volatilidad"
    elif adx >= 23 and ema_up and last["plus_di"] > last["minus_di"]:
        name = "tendencia_alcista"
    elif adx >= 23 and ema_dn and last["minus_di"] > last["plus_di"]:
        name = "tendencia_bajista"
    else:
        name = "lateral"
    return Regime(name, adx, vol_pct)


# Multiplicadores de peso por régimen
REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "tendencia_alcista": {"trend": 1.3, "momentum": 1.1, "patterns": 0.7, "structure": 1.0},
    "tendencia_bajista": {"trend": 1.3, "momentum": 1.1, "patterns": 0.7, "structure": 1.0},
    "lateral": {"trend": 0.6, "momentum": 1.0, "patterns": 1.3, "structure": 1.3},
    "alta_volatilidad": {"trend": 0.8, "momentum": 0.8, "patterns": 0.6, "positioning": 1.4},
}


@dataclass
class MarketRegime:
    state: str  # "expansión alcista" | "contracción bajista" | "acumulación/lateral"
    probability: float
    method: str


def hmm_market_regime(btc_daily: pd.DataFrame, n_states: int = 3) -> MarketRegime | None:
    """Ajusta un HMM gaussiano sobre BTC diario y etiqueta el estado actual."""
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:  # dependencia opcional
        return None
    close = btc_daily["close"].astype(float)
    ret = np.log(close).diff()
    vol = ret.rolling(10).std()
    feats = pd.concat([ret, vol], axis=1).dropna()
    if len(feats) < 150:
        return None
    X = feats.to_numpy()
    X = (X - X.mean(0)) / X.std(0)
    try:
        model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=7)
        model.fit(X)
        states = model.predict(X)
        post = model.predict_proba(X)[-1]
    except Exception as exc:  # convergencia numérica
        log.warning("HMM no convergió: %s", exc)
        return None

    # Etiquetar estados por retorno medio real (no normalizado)
    means = {s: feats.iloc[:, 0][states == s].mean() for s in range(n_states)}
    order = sorted(means, key=means.get)
    labels = {order[0]: "contracción bajista", order[-1]: "expansión alcista"}
    for s in order[1:-1]:
        labels[s] = "acumulación/lateral"
    cur = int(states[-1])
    return MarketRegime(labels[cur], float(post[cur]), "hmm")
