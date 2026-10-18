"""Auto-evaluación: mide si las señales pasadas acertaron y recalibra pesos.

Es la parte que convierte al sistema en un agente que aprende con evidencia:
cada señal se contrasta con lo que hizo el precio 24h/72h después, se calcula el
IC (Information Coefficient, Spearman score→retorno) de cada componente y, con
suficiente muestra, los pesos se ajustan dentro de un rango acotado [0.5x, 1.5x].
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import select

from ..market.exchange import MarketData
from ..storage.db import ComponentStat, Database, Signal, utcnow

log = logging.getLogger(__name__)
HORIZON_H = 72


def outcome_from_path(sig_price: float, plan: dict | None, path: pd.DataFrame) -> str:
    """Primer evento tocado: objetivo 1 o stop (si ambos en la misma vela, se asume stop)."""
    if not plan or not plan.get("targets"):
        return "sin_plan"
    stop, tgt = plan["stop"], plan["targets"][0]
    long = plan["direction"] == "long"
    for _, bar in path.iterrows():
        hit_stop = bar["low"] <= stop if long else bar["high"] >= stop
        hit_tgt = bar["high"] >= tgt if long else bar["low"] <= tgt
        if hit_stop:
            return "stop"
        if hit_tgt:
            return "target"
    return "abierta"


async def evaluate_signals(db: Database, md: MarketData, now: dt.datetime | None = None) -> int:
    now = now or utcnow()
    cutoff = now - dt.timedelta(hours=HORIZON_H)
    with db.session() as s:
        pending = list(
            s.scalars(
                select(Signal).where(Signal.kind == "full", Signal.evaluated.is_(False), Signal.ts <= cutoff).limit(2000)
            )
        )
    by_symbol: dict[str, list[Signal]] = defaultdict(list)
    for sig in pending:
        by_symbol[sig.symbol].append(sig)

    done = 0
    for symbol, sigs in by_symbol.items():
        since = min(sg.ts for sg in sigs)
        since = since if since.tzinfo else since.replace(tzinfo=dt.timezone.utc)
        try:
            rows = await md.call(md.spot.fetch_ohlcv, symbol, "1h", int(since.timestamp() * 1000), 1000)
        except Exception as exc:
            log.info("evaluación %s: %s", symbol, exc)
            continue
        candles = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        candles.index = pd.to_datetime(candles.pop("ts"), unit="ms", utc=True)
        with db.session() as s:
            for sg in sigs:
                ts = sg.ts if sg.ts.tzinfo else sg.ts.replace(tzinfo=dt.timezone.utc)
                path = candles[candles.index > ts]
                if len(path) < HORIZON_H:
                    continue
                sg = s.merge(sg)
                sg.ret_24h = float(path["close"].iloc[23] / sg.price - 1) * 100
                sg.ret_72h = float(path["close"].iloc[HORIZON_H - 1] / sg.price - 1) * 100
                sg.outcome = outcome_from_path(sg.price, sg.plan, path.iloc[:HORIZON_H])
                sg.evaluated = True
                done += 1
            s.commit()
    if done:
        update_component_stats(db)
    log.info("señales evaluadas: %d", done)
    return done


def update_component_stats(db: Database, min_n: int = 50) -> dict[str, dict]:
    with db.session() as s:
        rows = list(s.scalars(select(Signal).where(Signal.evaluated.is_(True), Signal.kind == "full")))
        if not rows:
            return {}
        df = pd.DataFrame([{**r.components, "_score": r.score, "_ret": r.ret_72h} for r in rows]).dropna(subset=["_ret"])
        stats: dict[str, dict] = {}
        for col in [c for c in df.columns if c != "_ret"]:
            sub = df[[col, "_ret"]].dropna()
            if len(sub) < 10:
                continue
            ic = float(sub[col].corr(sub["_ret"], method="spearman"))
            strong = sub[sub[col].abs() > 0.1]
            hit = float((np.sign(strong[col]) == np.sign(strong["_ret"])).mean()) if len(strong) else float("nan")
            mult = float(np.clip(1 + 3 * ic, 0.5, 1.5)) if len(sub) >= min_n and not np.isnan(ic) else 1.0
            name = "score_total" if col == "_score" else col
            stats[name] = {"ic": ic, "hit_rate": hit, "n": len(sub), "weight_mult": mult}
            st = s.get(ComponentStat, name) or ComponentStat(name=name)
            st.ic, st.hit_rate, st.n, st.weight_mult, st.updated = ic, hit, len(sub), mult, utcnow()
            s.add(st)
        s.commit()
    return stats


def performance_summary(db: Database, days: int = 30) -> dict:
    since = utcnow() - dt.timedelta(days=days)
    with db.session() as s:
        rows = list(
            s.scalars(select(Signal).where(Signal.evaluated.is_(True), Signal.ts >= since, Signal.kind == "full"))
        )
        stats = {c.name: {"ic": round(c.ic, 3), "n": c.n, "peso_x": round(c.weight_mult, 2)} for c in s.scalars(select(ComponentStat))}
    directional = [r for r in rows if abs(r.score) >= 25 and r.ret_72h is not None]
    if not directional:
        return {"n": 0, "componentes": stats}
    hits = [np.sign(r.score) == np.sign(r.ret_72h) for r in directional]
    outcomes = [r.outcome for r in directional if r.outcome in ("target", "stop")]
    return {
        "n": len(directional),
        "hit_rate_72h": float(np.mean(hits)),
        "target_vs_stop": f"{outcomes.count('target')}/{outcomes.count('stop')}",
        "componentes": stats,
    }
