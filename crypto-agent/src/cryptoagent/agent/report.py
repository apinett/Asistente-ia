"""Contexto del informe diario e informe por plantilla (sin LLM)."""

from __future__ import annotations

import datetime as dt

from ..analysis.scoring import SymbolAnalysis
from .serialize import DISCLAIMER, EMOJI, analysis_to_dict, fmt_price


def build_context(
    analyses: list[SymbolAnalysis],
    breadth: dict,
    macro: dict,
    market_regime: dict | None,
    performance: dict,
    top_k: int = 6,
) -> dict:
    ranked = sorted(analyses, key=lambda a: a.score * a.confidence, reverse=True)
    bulls = [a for a in ranked if a.score > 0][:top_k]
    bears = [a for a in reversed(ranked) if a.score < 0][:top_k]
    majors = {a.symbol: analysis_to_dict(a, detail=True) for a in analyses if a.symbol in ("BTC/USDT", "ETH/USDT")}
    return {
        "fecha_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "regimen_mercado": market_regime,
        "amplitud": breadth,
        "macro": macro,
        "mayores": majors,
        "top_alcistas": [analysis_to_dict(a, detail=False) for a in bulls],
        "top_bajistas": [analysis_to_dict(a, detail=False) for a in bears],
        "distribucion_scores": {
            lbl: sum(1 for a in analyses if a.label == lbl)
            for lbl in ("ALCISTA FUERTE", "ALCISTA", "NEUTRAL", "BAJISTA", "BAJISTA FUERTE")
        },
        "desempeno_senales": performance,
    }


def template_report(ctx: dict) -> str:
    L: list[str] = [f"📊 Informe diario cripto — {ctx['fecha_utc']} UTC", ""]
    reg = ctx.get("regimen_mercado") or {}
    if reg:
        L.append(f"Régimen (HMM sobre BTC): {reg.get('state')} (prob. {reg.get('probability', 0):.0%})")
    m = ctx.get("macro") or {}
    if "fear_greed" in m:
        fg = m["fear_greed"]
        L.append(f"Fear & Greed: {fg['value']} ({fg['label']}), hace 7 días {fg['hace_7d']}")
    if "global" in m:
        g = m["global"]
        L.append(f"Cap. total {g['market_cap_change_24h_pct']:+.2f}% 24h · dominancia BTC {g['btc_dominance']}%")
    if "stablecoins" in m:
        L.append(f"Stablecoins {m['stablecoins']['change_24h_pct']:+.2f}% 24h (liquidez disponible)")
    b = ctx.get("amplitud") or {}
    if b:
        L.append(
            f"Amplitud: {b['pct_above_ema50']}% sobre EMA50 diaria, {b['pct_above_ema200']}% sobre EMA200 · "
            f"{b['advancers_1d']} suben / {b['decliners_1d']} bajan"
        )
    L += ["", "Mayores:"]
    for sym, a in ctx.get("mayores", {}).items():
        L.append(f"{EMOJI.get(a['label'], '')} {sym} {fmt_price(a['price'])} — {a['label']} ({a['score']:+.0f})")
        lpf = a.get("positioning_lpf")
        if lpf and lpf.get("quadrant"):
            L.append(
                f"   LPF {lpf['score']:+.2f}: {lpf['quadrant'].replace('_', ' ')}, flujo {lpf.get('flow_leader') or 's/d'}"
            )
    for title, key in (("Más fuertes:", "top_alcistas"), ("Más débiles:", "top_bajistas")):
        L += ["", title]
        for a in ctx.get(key, []):
            L.append(f"{EMOJI.get(a['label'], '')} {a['symbol']} {a['score']:+.0f} (conf. {a['confidence']:.2f})")
            if a.get("highlights"):
                L.append(f"   {a['highlights'][0]}")
    perf = ctx.get("desempeno_senales") or {}
    if perf.get("n"):
        L += ["", f"Desempeño señales (n={perf['n']}): acierto direccional 72h {perf['hit_rate_72h']:.0%}"]
    L += ["", DISCLAIMER]
    return "\n".join(L)
