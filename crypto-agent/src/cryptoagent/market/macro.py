"""Contexto macro del mercado cripto (fuentes públicas gratuitas, sin API key)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

FNG_URL = "https://api.alternative.me/fng/?limit=8"
CG_GLOBAL = "https://api.coingecko.com/api/v3/global"
CG_STABLES = "https://api.coingecko.com/api/v3/coins/categories"


async def fetch_macro() -> dict:
    out: dict = {}
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "cryptoagent/1.0"}) as client:
        try:
            r = (await client.get(FNG_URL)).json()["data"]
            out["fear_greed"] = {
                "value": int(r[0]["value"]),
                "label": r[0]["value_classification"],
                "hace_7d": int(r[-1]["value"]),
            }
        except Exception as exc:
            log.info("Fear & Greed no disponible: %s", exc)
        try:
            g = (await client.get(CG_GLOBAL)).json()["data"]
            out["global"] = {
                "market_cap_usd": g["total_market_cap"]["usd"],
                "market_cap_change_24h_pct": round(g["market_cap_change_percentage_24h_usd"], 2),
                "btc_dominance": round(g["market_cap_percentage"]["btc"], 2),
                "eth_dominance": round(g["market_cap_percentage"]["eth"], 2),
            }
        except Exception as exc:
            log.info("CoinGecko global no disponible: %s", exc)
        try:
            cats = (await client.get(CG_STABLES)).json()
            st = next(c for c in cats if c.get("id") == "stablecoins")
            # Liquidez "seca" disponible para entrar al mercado: si crece, hay poder de compra nuevo
            out["stablecoins"] = {
                "market_cap_usd": st["market_cap"],
                "change_24h_pct": round(st.get("market_cap_change_24h") or 0, 3),
            }
        except Exception as exc:
            log.info("Stablecoins no disponible: %s", exc)
    return out
