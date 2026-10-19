"""Métricas de efectividad del agente (alimentan el dashboard).

"Acierto" = el signo del score coincide con el signo del retorno a 72h. Sólo cuentan
las señales con sesgo (|score| ≥ umbral de señal): las neutrales no predicen dirección.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import func, select

from ..storage.db import ComponentStat, Database, Signal, utcnow

CONF_BUCKETS = [(0.0, 0.4, "< 0.40"), (0.4, 0.6, "0.40–0.60"), (0.6, 0.8, "0.60–0.80"), (0.8, 1.01, "≥ 0.80")]
LABELS = ["ALCISTA FUERTE", "ALCISTA", "BAJISTA", "BAJISTA FUERTE"]


def r_multiple(price: float, plan: dict | None, outcome: str | None, ret_72h: float | None) -> float | None:
    """Resultado de la señal medido en múltiplos del riesgo (R) si se hubiera seguido el plan."""
    if not plan or not plan.get("targets") or plan.get("stop") is None:
        return None
    long = plan["direction"] == "long"
    risk_pct = abs(price - plan["stop"]) / price * 100
    if risk_pct <= 0:
        return None
    if outcome == "target":
        return float(plan.get("risk_reward") or abs(plan["targets"][0] - price) / abs(price - plan["stop"]))
    if outcome == "stop":
        return -1.0
    if ret_72h is None:
        return None
    return float((ret_72h if long else -ret_72h) / risk_pct)


def _frame(db: Database, since: dt.datetime, min_abs_score: float) -> pd.DataFrame:
    cols = (Signal.ts, Signal.symbol, Signal.price, Signal.score, Signal.label, Signal.confidence,
            Signal.ret_24h, Signal.ret_72h, Signal.outcome, Signal.plan)  # fmt: skip
    with db.session() as s:
        q = select(*cols).where(
            Signal.kind == "full",
            Signal.evaluated.is_(True),
            Signal.ts >= since,
            func.abs(Signal.score) >= min_abs_score,
        )
        rows = s.execute(q).all()  # tuplas: mucho más liviano que objetos ORM con miles de filas
    df = pd.DataFrame(rows, columns=[c.key for c in cols])
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["r"] = [r_multiple(p, pl, o, r72) for p, pl, o, r72 in zip(df["price"], df["plan"], df["outcome"], df["ret_72h"])]
    df = df.dropna(subset=["ret_72h"])
    df["hit"] = np.sign(df["score"]) == np.sign(df["ret_72h"])
    df["hit24"] = np.sign(df["score"]) == np.sign(df["ret_24h"].fillna(0))
    df["dir_ret"] = np.sign(df["score"]) * df["ret_72h"]
    return df


def _rate(x: pd.Series) -> float | None:
    return round(float(x.mean()), 4) if len(x) else None


def effectiveness(db: Database, days: int = 90, signal_threshold: float = 25, strong_threshold: float = 55) -> dict:
    since = utcnow() - dt.timedelta(days=days)
    df = _frame(db, since, signal_threshold)
    with db.session() as s:
        pending = s.scalar(
            select(func.count()).select_from(Signal).where(Signal.kind == "full", Signal.evaluated.is_(False))
        )
        total = s.scalar(select(func.count()).select_from(Signal).where(Signal.kind == "full"))
        first = s.scalar(select(func.min(Signal.ts)))
        comps = [
            {"name": c.name, "ic": round(c.ic, 4), "hit_rate": None if np.isnan(c.hit_rate) else round(c.hit_rate, 4), "n": c.n, "weight_mult": round(c.weight_mult, 2)}
            for c in s.scalars(select(ComponentStat).order_by(ComponentStat.ic.desc()))
        ]  # fmt: skip

    out: dict = {
        "days": days,
        "signals_total": total or 0,
        "signals_pending": pending or 0,
        "first_signal": first,
        "components": comps,
        "summary": {"n": 0},
        "daily": [],
        "by_confidence": [],
        "by_label": [],
    }
    if df.empty:
        return out

    strong = df[df["score"].abs() >= strong_threshold]
    outcomes = df["outcome"].value_counts()
    rr = df["r"].dropna()
    out["summary"] = {
        "n": int(len(df)),
        "hit_rate_72h": _rate(df["hit"]),
        "hit_rate_24h": _rate(df["hit24"]),
        "hit_rate_strong": _rate(strong["hit"]),
        "n_strong": int(len(strong)),
        "targets": int(outcomes.get("target", 0)),
        "stops": int(outcomes.get("stop", 0)),
        "expectancy_r": round(float(rr.mean()), 3) if len(rr) else None,
        "avg_dir_return_pct": round(float(df["dir_ret"].mean()), 3),
    }

    # Serie diaria + media móvil de 7 días ponderada por cantidad de señales
    d = df.assign(date=df["ts"].dt.tz_convert("UTC").dt.floor("D"))
    daily = d.groupby("date").agg(n=("hit", "size"), hits=("hit", "sum"))
    ds = d[d["score"].abs() >= strong_threshold].groupby("date").agg(n_s=("hit", "size"), hits_s=("hit", "sum"))
    daily = daily.join(ds, how="left").fillna(0)
    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_idx, fill_value=0)
    roll = daily.rolling(7, min_periods=1).sum()
    out["daily"] = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "n": int(row.n),
            "hit_rate": round(row.hits / row.n, 4) if row.n else None,
            "hit_rate_7d": round(roll.loc[idx, "hits"] / roll.loc[idx, "n"], 4) if roll.loc[idx, "n"] else None,
            "hit_rate_strong_7d": round(roll.loc[idx, "hits_s"] / roll.loc[idx, "n_s"], 4) if roll.loc[idx, "n_s"] else None,
        }
        for idx, row in daily.iterrows()
    ]

    for lo, hi, name in CONF_BUCKETS:
        b = df[(df["confidence"] >= lo) & (df["confidence"] < hi)]
        out["by_confidence"].append({"bucket": name, "n": int(len(b)), "hit_rate": _rate(b["hit"])})
    for lbl in LABELS:
        b = df[df["label"] == lbl]
        out["by_label"].append({"label": lbl, "n": int(len(b)), "hit_rate": _rate(b["hit"]), "avg_r": round(float(b["r"].dropna().mean()), 3) if b["r"].notna().any() else None})
    return out
