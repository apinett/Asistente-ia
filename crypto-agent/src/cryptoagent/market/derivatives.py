"""Datos de derivados para el análisis LPF (funding, OI, premium, ratios long/short).

Cada fuente se pide por separado y se degrada con gracia: si una falla, el análisis
sigue con las demás (LPF re-normaliza pesos sobre lo disponible).
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd

from ..analysis.positioning import DerivativesData
from .exchange import MarketData, perp_symbol

log = logging.getLogger(__name__)


def _series(rows: list[dict], value_key: str, ts_key: str = "timestamp") -> pd.Series | None:
    pts = [(int(r[ts_key]), float(r[value_key])) for r in rows if r.get(value_key) is not None and r.get(ts_key)]
    if not pts:
        return None
    s = pd.Series([v for _, v in pts], index=pd.to_datetime([t for t, _ in pts], unit="ms", utc=True))
    return s[~s.index.duplicated()].sort_index()


async def _safe(coro, what: str, symbol: str):
    try:
        return await coro
    except Exception as exc:  # una fuente caída no debe tumbar el análisis
        log.info("LPF %s sin %s: %s", symbol, what, str(exc)[:160])
        return None


async def fetch_derivatives(md: MarketData, symbol: str, period: str = "1h", limit: int = 500) -> DerivativesData | None:
    await md.load()
    psym = perp_symbol(symbol)
    if psym not in md.deriv.markets:
        return None
    pid = md.deriv.market(psym)["id"]
    d = md.deriv

    tasks = {
        "perp": _safe(md.candles(symbol, period, limit, market="perp"), "velas perp", symbol),
        "spot": _safe(md.candles(symbol, period, limit, market="spot"), "velas spot", symbol),
        "oi": _safe(md.call(d.fetch_open_interest_history, psym, period, None, min(limit, 500)), "open interest", symbol),
        "funding": _safe(md.call(d.fetch_funding_rate_history, psym, None, 200), "funding", symbol),
    }
    if md.is_binance:
        tasks["premium"] = _safe(md.call(d.fapiPublicGetPremiumIndex, {"symbol": pid}), "premium", symbol)
        lsp = {"symbol": pid, "period": period, "limit": min(limit, 500)}
        tasks["top_ls"] = _safe(md.call(d.fapiDataGetTopLongShortPositionRatio, lsp), "top L/S", symbol)
        tasks["global_ls"] = _safe(md.call(d.fapiDataGetGlobalLongShortAccountRatio, lsp), "global L/S", symbol)

    res = dict(zip(tasks, await asyncio.gather(*tasks.values())))
    perp = res.get("perp")
    if perp is None or len(perp) < 30:
        return None

    oi = _series(res["oi"] or [], "openInterestValue")
    funding = _series(res["funding"] or [], "fundingRate")
    premium = None
    if res.get("premium"):
        p = res["premium"]
        mark, index = float(p.get("markPrice") or 0), float(p.get("indexPrice") or 0)
        premium = (mark - index) / index * 100 if index else None
    top_ls = _series(res.get("top_ls") or [], "longShortRatio")
    global_ls = _series(res.get("global_ls") or [], "longShortRatio")

    return DerivativesData(
        perp=perp,
        open_interest=oi,
        funding=funding,
        premium_pct=premium,
        top_ls_ratio=top_ls,
        global_ls_ratio=global_ls,
        spot=res.get("spot"),
    )
