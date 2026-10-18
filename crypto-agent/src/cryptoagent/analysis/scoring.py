"""Motor de confluencia: combina componentes y temporalidades en un score -100..100.

score = Σ_c  w_c · m_regimen(c) · m_adaptativo(c) · s_c   /  Σ pesos
donde s_c ∈ [-1, 1] es el score del componente promediado entre temporalidades,
y el momentum/tendencia se multiplican por `momentum_quality` (de LPF).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .candles import CandleResult, analyze_candles
from .momentum import MomentumResult, analyze_momentum
from .positioning import PositioningResult
from .regime import REGIME_WEIGHTS, Regime, rule_regime
from .structure import StructureResult, analyze_structure

TF_COMPONENTS = ("trend", "momentum", "volume", "patterns", "structure")


@dataclass
class TimeframeAnalysis:
    timeframe: str
    close: float
    atr: float
    regime: Regime
    trend: float
    volume: float
    squeeze: bool
    momentum: MomentumResult
    candles: CandleResult
    structure: StructureResult

    def components(self) -> dict[str, float]:
        return {
            "trend": self.trend,
            "momentum": self.momentum.score,
            "volume": self.volume,
            "patterns": self.candles.score,
            "structure": self.structure.score,
        }


@dataclass
class TradePlan:
    direction: str  # "long" | "short"
    entry_low: float
    entry_high: float
    stop: float
    targets: list[float]
    risk_reward: float
    invalidation: str


@dataclass
class SymbolAnalysis:
    symbol: str
    price: float
    score: float
    label: str
    confidence: float
    components: dict[str, float]
    timeframes: dict[str, TimeframeAnalysis]
    positioning: PositioningResult | None = None
    relative_strength: float | None = None
    alignment: float = 0.0
    plan: TradePlan | None = None
    highlights: list[str] = field(default_factory=list)


def trend_score(df: pd.DataFrame) -> float:
    last = df.iloc[-1]
    s = 0.0
    s += 0.25 if last["close"] > last["ema20"] else -0.25
    s += 0.25 if last["ema20"] > last["ema50"] else -0.25
    if not np.isnan(last["ema200"]):
        s += 0.25 if last["ema50"] > last["ema200"] else -0.25
    s += 0.25 * float(last["supertrend_dir"])
    adx = 0.0 if np.isnan(last["adx"]) else float(last["adx"])
    strength = np.clip((adx - 15) / 25, 0, 1)
    return float(np.clip(s * (0.5 + 0.5 * strength), -1, 1))


def volume_score(df: pd.DataFrame, window: int = 20) -> float:
    w = df.iloc[-window:]
    obv = w["obv"].to_numpy()
    x = np.arange(len(obv))
    slope = np.polyfit(x, obv, 1)[0] if len(obv) > 2 else 0.0
    avg_vol = max(w["volume"].mean(), 1e-12)
    obv_part = float(np.clip(slope / avg_vol, -1, 1))
    cmf = df["cmf"].iloc[-1]
    cmf_part = 0.0 if np.isnan(cmf) else float(np.clip(cmf * 4, -1, 1))
    last = df.iloc[-1]
    rv = last["rel_volume"]
    candle_dir = np.sign(last["close"] - last["open"])
    rv_part = float(candle_dir * np.clip((rv - 1), 0, 1)) if not np.isnan(rv) else 0.0
    return float(np.clip(0.4 * obv_part + 0.4 * cmf_part + 0.2 * rv_part, -1, 1))


def analyze_timeframe(df: pd.DataFrame, timeframe: str) -> TimeframeAnalysis:
    """`df` debe traer indicadores (ver indicators.compute_indicators)."""
    regime = rule_regime(df)
    structure = analyze_structure(df)
    momentum = analyze_momentum(df, regime.name)
    candles = analyze_candles(
        df,
        supports=[lv.price for lv in structure.supports],
        resistances=[lv.price for lv in structure.resistances],
    )
    last = df.iloc[-1]
    return TimeframeAnalysis(
        timeframe=timeframe,
        close=float(last["close"]),
        atr=float(last["atr"]),
        regime=regime,
        trend=trend_score(df),
        volume=volume_score(df),
        squeeze=bool(last["squeeze"]),
        momentum=momentum,
        candles=candles,
        structure=structure,
    )


def label_for(score: float, strong: float, signal: float) -> str:
    if score >= strong:
        return "ALCISTA FUERTE"
    if score >= signal:
        return "ALCISTA"
    if score <= -strong:
        return "BAJISTA FUERTE"
    if score <= -signal:
        return "BAJISTA"
    return "NEUTRAL"


def build_plan(tf: TimeframeAnalysis, direction: int) -> TradePlan | None:
    if direction == 0 or not tf.atr or np.isnan(tf.atr):
        return None
    c, a = tf.close, tf.atr
    sup = [lv.price for lv in tf.structure.supports]
    res = [lv.price for lv in tf.structure.resistances]
    if direction > 0:
        near_sup = next((s for s in sup if c - s <= 2.5 * a), None)
        stop = (near_sup - 0.3 * a) if near_sup else c - 2 * a
        entry_low = max(near_sup or c - 0.5 * a, c - 0.7 * a)
        risk = c - stop
        targets = [r for r in res if r - c >= risk][:2] or [c + 1.5 * risk, c + 3 * risk]
        inval = f"cierre por debajo de {stop:.6g}"
        rr = (targets[0] - c) / risk if risk > 0 else 0
        return TradePlan("long", float(entry_low), float(c), float(stop), [float(t) for t in targets], float(rr), inval)
    near_res = next((r for r in res if r - c <= 2.5 * a), None)
    stop = (near_res + 0.3 * a) if near_res else c + 2 * a
    entry_high = min(near_res or c + 0.5 * a, c + 0.7 * a)
    risk = stop - c
    targets = [s for s in sup if c - s >= risk][:2] or [c - 1.5 * risk, c - 3 * risk]
    inval = f"cierre por encima de {stop:.6g}"
    rr = (c - targets[0]) / risk if risk > 0 else 0
    return TradePlan("short", float(c), float(entry_high), float(stop), [float(t) for t in targets], float(rr), inval)


def combine(
    symbol: str,
    tfs: dict[str, TimeframeAnalysis],
    tf_weights: dict[str, float],
    base_weights: dict[str, float],
    primary_tf: str,
    positioning: PositioningResult | None = None,
    rel_strength: float | None = None,
    adaptive: dict[str, float] | None = None,
    strong: float = 55,
    signal: float = 25,
) -> SymbolAnalysis:
    avail = {tf: w for tf, w in tf_weights.items() if tf in tfs}
    wsum = sum(avail.values()) or 1.0
    comps: dict[str, float] = {
        c: sum(avail[tf] * tfs[tf].components()[c] for tf in avail) / wsum for c in TF_COMPONENTS
    }
    if positioning is not None:
        comps["positioning"] = positioning.score
    if rel_strength is not None:
        comps["relative_strength"] = rel_strength

    primary = tfs.get(primary_tf) or next(iter(tfs.values()))
    regime_mult = REGIME_WEIGHTS.get(primary.regime.name, {})
    quality = positioning.momentum_quality if positioning is not None else 1.0
    adaptive = adaptive or {}

    num = den = 0.0
    for c, s in comps.items():
        w = base_weights.get(c, 0.0) * regime_mult.get(c, 1.0) * adaptive.get(c, 1.0)
        if c in ("momentum", "trend"):
            s = float(np.clip(s * quality, -1, 1))
        num += w * s
        den += w
    raw = num / den if den else 0.0
    score = round(float(np.clip(raw, -1, 1)) * 100, 1)

    # Alineación multi-timeframe: % de temporalidades cuyo sesgo coincide con el score final
    tf_bias = {tf: np.mean(list(tfs[tf].components().values())) for tf in avail}
    agree = [avail[tf] for tf, b in tf_bias.items() if np.sign(b) == np.sign(score) and score != 0]
    alignment = sum(agree) / wsum
    completeness = (len(avail) / max(len(tf_weights), 1)) * (1.0 if positioning is not None else 0.85)
    confidence = round(float(np.clip(0.5 * alignment + 0.5 * min(abs(score) / 70, 1), 0, 1) * completeness), 2)

    label = label_for(score, strong, signal)
    direction = 1 if score >= signal else -1 if score <= -signal else 0
    plan = build_plan(primary, direction)

    highlights: list[str] = []
    for tf, a in tfs.items():
        highlights += [f"[{tf}] {d.replace('_', ' ')}" for d in a.momentum.divergences]
        highlights += [f"[{tf}] {n}" for n in a.momentum.notes]
        if a.structure.last_event:
            highlights.append(f"[{tf}] {a.structure.last_event.replace('_', ' ')}")
        if a.squeeze:
            highlights.append(f"[{tf}] compresión de volatilidad (squeeze): posible expansión")
        highlights += [f"[{tf}] vela {h.label} ({', '.join(h.context)})" for h in a.candles.hits[:2] if h.weight >= 0.5]
    if positioning is not None:
        highlights += [f"[LPF] {n}" for n in positioning.notes]
        if positioning.quadrant:
            highlights.append(f"[LPF] cuadrante precio/OI: {positioning.quadrant.replace('_', ' ')}")
        if positioning.flow_leader:
            highlights.append(f"[LPF] flujo liderado por {positioning.flow_leader}")

    return SymbolAnalysis(
        symbol=symbol,
        price=primary.close,
        score=score,
        label=label,
        confidence=confidence,
        components={k: round(v, 3) for k, v in comps.items()},
        timeframes=tfs,
        positioning=positioning,
        relative_strength=rel_strength,
        alignment=round(alignment, 2),
        plan=plan,
        highlights=highlights,
    )
