"""Conversión de resultados a dict (para DB, API, LLM) y a texto (alertas)."""

from __future__ import annotations

from dataclasses import asdict

from ..analysis.scoring import SymbolAnalysis

EMOJI = {"ALCISTA FUERTE": "🟢🟢", "ALCISTA": "🟢", "NEUTRAL": "⚪", "BAJISTA": "🔴", "BAJISTA FUERTE": "🔴🔴"}
DISCLAIMER = "⚠️ Análisis automatizado con fines informativos. No es asesoramiento financiero."


def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 1:
        return f"{p:,.3f}"
    return f"{p:.6g}"


def analysis_to_dict(a: SymbolAnalysis, detail: bool = True) -> dict:
    out = {
        "symbol": a.symbol,
        "price": a.price,
        "score": a.score,
        "label": a.label,
        "confidence": a.confidence,
        "alignment": a.alignment,
        "components": a.components,
        "relative_strength_vs_btc": a.relative_strength,
        "plan": asdict(a.plan) if a.plan else None,
        "highlights": a.highlights[:12],
    }
    if not detail:
        return out
    out["timeframes"] = {
        tf: {
            "regime": t.regime.name,
            "adx": round(t.regime.adx, 1),
            "trend": round(t.trend, 3),
            "volume": round(t.volume, 3),
            "squeeze": t.squeeze,
            "atr": t.atr,
            "momentum": {
                "score": round(t.momentum.score, 3),
                "rsi": round(t.momentum.rsi, 1),
                "macd_hist": t.momentum.macd_hist,
                "stochrsi_k": round(t.momentum.stochrsi_k, 1),
                "roc10": round(t.momentum.roc10, 2),
                "divergences": t.momentum.divergences,
            },
            "patterns": [{"name": h.label, "bars_ago": h.bars_ago, "weight": round(h.weight, 2), "context": h.context} for h in t.candles.hits],
            "structure": {
                "trend": t.structure.trend,
                "last_event": t.structure.last_event,
                "supports": [round(lv.price, 8) for lv in t.structure.supports],
                "resistances": [round(lv.price, 8) for lv in t.structure.resistances],
                "bullish_fvg": t.structure.bullish_fvg,
                "bearish_fvg": t.structure.bearish_fvg,
            },
        }
        for tf, t in a.timeframes.items()
    }
    if a.positioning is not None:
        p = a.positioning.to_dict()
        for k in ("liquidation_above", "liquidation_below"):
            p[k] = [{"price": c["price"], "usd": round(c["notional_usd"]), "dist_pct": round(c["distance_pct"], 2)} for c in p[k]]
        out["positioning_lpf"] = p
    return out


def alert_text(a: SymbolAnalysis, primary_tf: str, prefix: str = "") -> str:
    lines = [
        f"{prefix}{EMOJI.get(a.label, '')} {a.symbol} — {a.label}",
        f"Score {a.score:+.0f}/100 · confianza {a.confidence:.2f} · precio {fmt_price(a.price)}",
    ]
    if a.plan:
        p = a.plan
        tg = " / ".join(fmt_price(t) for t in p.targets)
        lines.append(
            f"Plan ({primary_tf}, {p.direction}): entrada {fmt_price(p.entry_low)}–{fmt_price(p.entry_high)} | "
            f"stop {fmt_price(p.stop)} | objetivos {tg} | R:R {p.risk_reward:.1f}"
        )
    if a.positioning is not None and a.positioning.funding_annualized_pct is not None:
        pos = a.positioning
        lines.append(
            f"LPF {pos.score:+.2f} · funding {pos.funding_annualized_pct:.1f}% anual · "
            f"OI {pos.oi_change_pct or 0:+.1f}% · calidad momentum x{pos.momentum_quality:.2f}"
        )
    if a.highlights:
        lines.append("Claves:")
        lines += [f"• {h}" for h in a.highlights[:6]]
    lines.append(DISCLAIMER)
    return "\n".join(lines)
