"""Nivel de confianza (readiness): ¿el agente demostró, con datos, que merece operar real?

Se evalúan SÓLO las señales que el módulo de trading habría ejecutado (largas, con
score, confianza y R:R mínimos), midiendo el resultado en múltiplos del riesgo (R).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import func, select

from ..agent.stats import r_multiple
from ..config import AgentConfig
from ..storage.db import ComponentStat, Database, Signal, Trade, utcnow


def _check(key: str, label: str, value, threshold, ok: bool, progress: float, fmt: str = "{}") -> dict:
    return {
        "key": key,
        "label": label,
        "value": value,
        "threshold": threshold,
        "display": fmt.format(value) if value is not None else "sin datos",
        "ok": bool(ok),
        "progress": float(np.clip(progress, 0, 1)),
    }


def qualifies(score: float, confidence: float, plan: dict | None, cfg: AgentConfig) -> bool:
    t = cfg.trading
    return bool(
        plan
        and plan.get("direction") == "long"
        and score >= t.min_score
        and confidence >= t.min_confidence
        and (plan.get("risk_reward") or 0) >= t.min_risk_reward
    )


def compute_readiness(db: Database, cfg: AgentConfig) -> dict:
    r = cfg.trading.readiness
    with db.session() as s:
        first = s.scalar(select(func.min(Signal.ts)).where(Signal.kind == "full"))
        n_eval = s.scalar(select(func.count()).select_from(Signal).where(Signal.kind == "full", Signal.evaluated.is_(True))) or 0
        q_rows = [
            r_multiple(x.price, x.plan, x.outcome, x.ret_72h)
            for x in s.scalars(
                select(Signal).where(Signal.kind == "full", Signal.evaluated.is_(True), Signal.score >= cfg.trading.min_score)
            )
            if qualifies(x.score, x.confidence, x.plan, cfg)
        ]
        ic_row = s.get(ComponentStat, "score_total")
        paper = list(s.scalars(select(Trade).where(Trade.mode == "paper", Trade.status == "closed")))

    days = 0.0
    if first is not None:
        first = first if first.tzinfo else first.replace(tzinfo=dt.timezone.utc)
        days = (utcnow() - first).total_seconds() / 86400
    rs = [x for x in q_rows if x is not None]
    hit = float(np.mean([x > 0 for x in rs])) if rs else None
    expectancy = float(np.mean(rs)) if rs else None
    ic = ic_row.ic if ic_row and ic_row.n >= 50 and not np.isnan(ic_row.ic) else None
    gains = sum(t.pnl_usd for t in paper if (t.pnl_usd or 0) > 0)
    losses = -sum(t.pnl_usd for t in paper if (t.pnl_usd or 0) < 0)
    pf = (gains / losses) if losses > 0 else (float("inf") if gains > 0 else None)

    checks = [
        _check("days", "Días de historial", round(days, 1), r.min_days, days >= r.min_days, days / r.min_days, "{} días"),
        _check("evaluated", "Señales evaluadas", n_eval, r.min_evaluated, n_eval >= r.min_evaluated, n_eval / r.min_evaluated),
        _check("qualifying", "Señales operables evaluadas", len(rs), r.min_qualifying, len(rs) >= r.min_qualifying, len(rs) / r.min_qualifying),
        _check(
            "hit_rate", "Acierto de señales operables", None if hit is None else round(hit * 100, 1), round(r.min_hit_rate * 100, 1),
            hit is not None and len(rs) >= 10 and hit >= r.min_hit_rate,
            0 if hit is None else (hit - 0.5) / max(r.min_hit_rate - 0.5, 1e-9), "{}%",
        ),
        _check(
            "expectancy", "Expectativa por operación", None if expectancy is None else round(expectancy, 3), r.min_expectancy_r,
            expectancy is not None and len(rs) >= 10 and expectancy >= r.min_expectancy_r,
            0 if expectancy is None else expectancy / r.min_expectancy_r, "{} R",
        ),
        _check("ic", "IC del score total", None if ic is None else round(ic, 4), r.min_ic, ic is not None and ic >= r.min_ic, 0 if ic is None else ic / r.min_ic),
        _check("paper_trades", "Operaciones simuladas cerradas", len(paper), r.min_paper_trades, len(paper) >= r.min_paper_trades, len(paper) / r.min_paper_trades),
        _check(
            "profit_factor", "Profit factor simulado", None if pf is None else (round(pf, 2) if pf != float("inf") else "∞"), r.min_profit_factor,
            pf is not None and len(paper) >= r.min_paper_trades and pf >= r.min_profit_factor,
            0 if pf is None else min(pf, 10) / r.min_profit_factor,
        ),
    ]  # fmt: skip
    level = round(float(np.mean([c["progress"] for c in checks])) * 100, 1)
    return {"level_pct": level, "ready_for_live": all(c["ok"] for c in checks), "checks": checks}
