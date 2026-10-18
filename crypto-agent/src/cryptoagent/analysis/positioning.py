"""LPF — Leverage & Positioning Flow (Flujo de Posicionamiento y Apalancamiento).

El análisis "nuevo" del agente. En el mercado cripto actual la formación de precio
la dominan los perpetuos: el volumen de derivados supera varias veces al spot y los
movimientos bruscos suelen ser cascadas de liquidaciones, no cambios de fundamentales.
El análisis técnico clásico mira sólo precio y volumen; LPF mira QUIÉN está empujando
el precio, CON CUÁNTO apalancamiento y DÓNDE están las posiciones que pueden ser
forzadas a cerrar. Todo con datos públicos y gratuitos de Binance Futures.

Seis bloques:
  1. Cuadrante Precio/Open Interest: ¿entra dinero nuevo o se cierran posiciones?
  2. Hacinamiento (crowding): z-score del funding + premium del perpetuo vs índice.
  3. Liderazgo del flujo: CVD (delta agresor) spot vs perpetuo. Subas lideradas por
     spot son más sostenibles que subas lideradas por apalancamiento.
  4. Smart vs retail: ratio long/short de top traders vs ratio de cuentas globales.
  5. Riesgo de squeeze: posiciones apalancadas acumulándose contra el precio.
  6. Mapa estimado de liquidaciones: dónde se liquidarían las posiciones abiertas
     (por ΔOI y niveles de apalancamiento típicos). Funcionan como imanes de precio.

Además produce `momentum_quality`: un multiplicador que ajusta el momentum técnico
según la calidad del flujo que lo sostiene ("momentum ajustado por apalancamiento").
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd


@dataclass
class DerivativesData:
    perp: pd.DataFrame  # OHLCV del perpetuo (+ taker_buy_volume si existe), resolución `period`
    open_interest: pd.Series | None = None  # OI en USD, misma resolución
    funding: pd.Series | None = None  # historial de funding (cada 8h)
    premium_pct: float | None = None  # (mark - index) / index * 100
    top_ls_ratio: pd.Series | None = None  # long/short de posiciones de top traders
    global_ls_ratio: pd.Series | None = None  # long/short de cuentas (retail)
    spot: pd.DataFrame | None = None  # OHLCV spot (+ taker_buy_volume)


@dataclass
class LiquidationCluster:
    price: float
    notional_usd: float
    side: str  # "longs" (debajo del precio) | "shorts" (encima)
    distance_pct: float


@dataclass
class PositioningResult:
    score: float
    momentum_quality: float
    quadrant: str | None = None
    price_change_pct: float | None = None
    oi_change_pct: float | None = None
    funding_rate: float | None = None
    funding_annualized_pct: float | None = None
    funding_z: float | None = None
    premium_pct: float | None = None
    spot_delta: float | None = None
    perp_delta: float | None = None
    flow_leader: str | None = None
    smart_vs_retail: float | None = None
    squeeze_risk: str | None = None
    liquidation_above: list[LiquidationCluster] = field(default_factory=list)
    liquidation_below: list[LiquidationCluster] = field(default_factory=list)
    liquidity_imbalance: float | None = None
    components: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


COMPONENT_WEIGHTS = {
    "quadrant": 0.25,
    "crowding": 0.20,
    "flow": 0.25,
    "smart_money": 0.15,
    "squeeze": 0.10,
    "liquidity": 0.05,
}


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def oi_price_quadrant(price: pd.Series, oi: pd.Series, window: int) -> tuple[str, float, float, float]:
    """Clasifica la ventana en uno de los 4 cuadrantes clásicos precio/OI."""
    p = price.iloc[-window - 1 :]
    o = oi.sort_index().reindex(p.index, method="ffill").dropna()  # as-of: último OI conocido en cada vela
    if len(o) < 2:
        return "sin_datos", 0.0, 0.0, 0.0
    dp = _pct(p.iloc[-1], p.iloc[0])
    doi = _pct(o.iloc[-1], o.iloc[0])
    strength = min(1.0, abs(doi) / 3.0)  # 3% de cambio de OI en la ventana = señal plena
    if dp >= 0 and doi >= 0:
        return "nuevos_largos", dp, doi, 0.6 * strength
    if dp >= 0 and doi < 0:
        return "cierre_de_cortos", dp, doi, 0.15 * strength
    if dp < 0 and doi >= 0:
        return "nuevos_cortos", dp, doi, -0.6 * strength
    return "liquidacion_de_largos", dp, doi, -0.15 * strength


def taker_delta(df: pd.DataFrame | None, window: int) -> float | None:
    """Delta agresor normalizado en la ventana: (compras_taker - ventas_taker) / volumen ∈ [-1, 1]."""
    if df is None or "taker_buy_volume" not in df or df["taker_buy_volume"].isna().all():
        return None
    w = df.iloc[-window:]
    vol = w["volume"].sum()
    if vol <= 0:
        return None
    return float((2 * w["taker_buy_volume"].sum() - vol) / vol)


def estimate_liquidations(
    perp: pd.DataFrame,
    oi: pd.Series,
    tiers: dict[int, float],
    bin_pct: float = 0.5,
    max_distance_pct: float = 15.0,
) -> tuple[list[LiquidationCluster], list[LiquidationCluster], float | None]:
    """Mapa aproximado de liquidaciones pendientes.

    Cada aumento de OI en una vela se asume como posiciones nuevas abiertas al cierre,
    repartidas entre largos/cortos según el flujo taker de esa vela y entre niveles de
    apalancamiento según `tiers`. Un nivel se descarta si el precio ya lo atravesó
    (esas posiciones ya fueron liquidadas). Es una estimación, no el libro real.
    """
    df = perp[["high", "low", "close", "volume"]].copy()
    df["tbv"] = perp["taker_buy_volume"] if "taker_buy_volume" in perp else np.nan
    df["oi"] = oi.sort_index().reindex(df.index, method="ffill")
    df = df.dropna(subset=["oi"])
    if len(df) < 10:
        return [], [], None

    d_oi = df["oi"].diff().clip(lower=0).fillna(0).to_numpy()
    long_frac = (df["tbv"] / df["volume"].replace(0, np.nan)).fillna(0.5).clip(0.2, 0.8).to_numpy()
    close = df["close"].to_numpy()
    low = df["low"].to_numpy()
    high = df["high"].to_numpy()
    # mínimo/máximo FUTURO a cada vela (para saber si el nivel ya fue barrido)
    fut_min = np.append(np.minimum.accumulate(low[::-1])[::-1][1:], np.inf)
    fut_max = np.append(np.maximum.accumulate(high[::-1])[::-1][1:], -np.inf)

    price_now = close[-1]
    bins: dict[tuple[str, int], float] = {}
    for i in np.nonzero(d_oi > 0)[0]:
        for lev, w in tiers.items():
            long_liq = close[i] * (1 - 1 / lev)
            short_liq = close[i] * (1 + 1 / lev)
            if fut_min[i] > long_liq:
                key = ("longs", int(round(_pct(long_liq, price_now) / bin_pct)))
                bins[key] = bins.get(key, 0.0) + d_oi[i] * long_frac[i] * w
            if fut_max[i] < short_liq:
                key = ("shorts", int(round(_pct(short_liq, price_now) / bin_pct)))
                bins[key] = bins.get(key, 0.0) + d_oi[i] * (1 - long_frac[i]) * w

    above, below = [], []
    for (side, b), notional in bins.items():
        dist = b * bin_pct
        if abs(dist) > max_distance_pct or notional <= 0:
            continue
        cl = LiquidationCluster(float(price_now * (1 + dist / 100)), float(notional), side, float(dist))
        (above if dist > 0 else below).append(cl)
    above.sort(key=lambda x: -x.notional_usd)
    below.sort(key=lambda x: -x.notional_usd)

    near_above = sum(c.notional_usd for c in above if c.distance_pct <= 5)
    near_below = sum(c.notional_usd for c in below if c.distance_pct >= -5)
    tot = near_above + near_below
    imbalance = (near_above - near_below) / tot if tot > 0 else None
    return above[:3], below[:3], imbalance


def analyze_positioning(
    data: DerivativesData,
    lookback: int = 24,
    leverage_tiers: dict[int, float] | None = None,
    momentum_sign: float = 0.0,
) -> PositioningResult:
    tiers = leverage_tiers or {10: 0.35, 25: 0.35, 50: 0.2, 100: 0.1}
    comp: dict[str, float] = {}
    notes: list[str] = []
    res = PositioningResult(score=0.0, momentum_quality=1.0)
    price = data.perp["close"]
    res.price_change_pct = _pct(price.iloc[-1], price.iloc[-lookback - 1]) if len(price) > lookback else None

    # 1. Cuadrante precio / OI
    if data.open_interest is not None and len(data.open_interest) > lookback:
        q, dp, doi, s = oi_price_quadrant(price, data.open_interest, lookback)
        res.quadrant, res.oi_change_pct = q, doi
        comp["quadrant"] = s

    # 2. Hacinamiento: funding z-score (contrarian) + premium
    if data.funding is not None and len(data.funding) >= 10:
        f = data.funding.astype(float)
        hist = f.iloc[-90:]  # ~30 días de funding cada 8h
        sd = hist.std()
        z = float((f.iloc[-1] - hist.mean()) / sd) if sd and sd > 0 else 0.0
        res.funding_rate = float(f.iloc[-1])
        res.funding_annualized_pct = float(f.iloc[-1] * 3 * 365 * 100)
        res.funding_z = z
        crowd = -np.clip(z / 2.5, -1, 1) if abs(z) > 1 else -0.1 * z
        if res.funding_annualized_pct > 40:
            crowd -= 0.3
            notes.append(f"funding muy alto ({res.funding_annualized_pct:.0f}% anual): largos hacinados")
        elif res.funding_annualized_pct < -15:
            crowd += 0.3
            notes.append("funding negativo: cortos pagando, combustible para short squeeze")
        if data.premium_pct is not None:
            res.premium_pct = data.premium_pct
            if data.premium_pct > 0.1:
                crowd -= 0.2
            elif data.premium_pct < -0.1:
                crowd += 0.2
        comp["crowding"] = float(np.clip(crowd, -1, 1))

    # 3. Liderazgo del flujo: spot vs perpetuo
    sd_ = taker_delta(data.spot, lookback)
    pd_ = taker_delta(data.perp, lookback)
    res.spot_delta, res.perp_delta = sd_, pd_
    if sd_ is not None:
        flow = float(np.clip(10 * (0.7 * sd_ + 0.3 * (pd_ or 0.0)), -1, 1))
        dp = res.price_change_pct or 0.0
        if dp > 0 and sd_ > 0.01 and sd_ >= (pd_ or 0):
            res.flow_leader = "spot (suba sana)"
        elif dp > 0 and sd_ <= 0 and (pd_ or 0) > 0:
            res.flow_leader = "perpetuos (suba frágil, apalancada)"
            flow -= 0.4
        elif dp < 0 and sd_ > 0.01:
            res.flow_leader = "absorción spot (compran la caída)"
            flow += 0.3
        elif dp < 0 and sd_ < -0.01:
            res.flow_leader = "venta spot (distribución)"
        else:
            res.flow_leader = "mixto"
        comp["flow"] = float(np.clip(flow, -1, 1))

    # 4. Smart money vs retail
    if data.top_ls_ratio is not None and len(data.top_ls_ratio) > lookback:
        top = data.top_ls_ratio.astype(float)
        sm = float(np.clip(np.log(top.iloc[-1] / top.iloc[-lookback - 1]) * 3, -1, 1)) * 0.5
        if data.global_ls_ratio is not None and len(data.global_ls_ratio):
            div = float(np.log(top.iloc[-1]) - np.log(float(data.global_ls_ratio.iloc[-1])))
            res.smart_vs_retail = div
            sm += float(np.clip(div * 2, -1, 1)) * 0.5
            if div > 0.25:
                notes.append("top traders más largos que el retail")
            elif div < -0.25:
                notes.append("retail más largo que los top traders (señal de cautela)")
        comp["smart_money"] = float(np.clip(sm, -1, 1))

    # 5. Riesgo de squeeze
    if res.funding_z is not None and res.oi_change_pct is not None:
        dp = res.price_change_pct or 0.0
        if res.funding_z < -1 and res.oi_change_pct > 2 and dp >= -0.5:
            res.squeeze_risk = "short_squeeze"
            comp["squeeze"] = 0.7
            notes.append("cortos acumulándose con funding negativo y precio sosteniéndose")
        elif res.funding_z > 1 and res.oi_change_pct > 2 and dp <= 0.5:
            res.squeeze_risk = "long_squeeze"
            comp["squeeze"] = -0.7
            notes.append("largos acumulándose con funding alto y precio sin avanzar")
        else:
            comp["squeeze"] = 0.0
        if res.quadrant == "liquidacion_de_largos" and res.oi_change_pct < -5 and res.funding_z < -1:
            res.quadrant = "capitulacion"
            comp["quadrant"] = 0.3
            notes.append("capitulación: fuerte caída de OI y funding negativo (suele marcar suelos locales)")

    # 6. Mapa de liquidaciones
    if data.open_interest is not None:
        above, below, imb = estimate_liquidations(data.perp, data.open_interest, tiers)
        res.liquidation_above, res.liquidation_below, res.liquidity_imbalance = above, below, imb
        if imb is not None:
            comp["liquidity"] = float(np.clip(imb, -1, 1)) * 0.6

    if comp:
        wsum = sum(COMPONENT_WEIGHTS[k] for k in comp)
        res.score = float(np.clip(sum(COMPONENT_WEIGHTS[k] * v for k, v in comp.items()) / wsum, -1, 1))
    res.components = comp
    res.notes = notes
    res.momentum_quality = momentum_quality(res, momentum_sign)
    return res


def momentum_quality(res: PositioningResult, momentum_sign: float) -> float:
    """Multiplicador 0.6–1.3 del momentum técnico según la calidad del flujo que lo sostiene."""
    if momentum_sign == 0:
        return 1.0
    q = 1.0
    up = momentum_sign > 0
    if res.quadrant in ("nuevos_largos",) and up or res.quadrant == "nuevos_cortos" and not up:
        q += 0.15  # entra dinero nuevo a favor del movimiento
    if res.quadrant == "cierre_de_cortos" and up or res.quadrant == "liquidacion_de_largos" and not up:
        q -= 0.15  # movimiento por cierre forzado: suele agotarse
    if res.flow_leader:
        if res.flow_leader.startswith("spot") and up or res.flow_leader.startswith("venta spot") and not up:
            q += 0.15
        if res.flow_leader.startswith("perpetuos") and up:
            q -= 0.2
    if res.squeeze_risk == "long_squeeze" and up or res.squeeze_risk == "short_squeeze" and not up:
        q -= 0.15
    return float(np.clip(q, 0.6, 1.3))
