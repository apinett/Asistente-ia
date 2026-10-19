"""Ejecución de órdenes. Mismo contrato para simulado (paper) y real (live).

El broker real usa la API unificada de ccxt sobre Binance **spot**: sin apalancamiento
y sin posibilidad de perder más de lo invertido. Las API keys deben tener permiso
sólo de trading spot (nunca de retiro) y restricción a la IP del VPS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

import ccxt.async_support as ccxt

log = logging.getLogger(__name__)

PriceSource = Callable[[list[str]], Awaitable[dict[str, float]]]


@dataclass
class Fill:
    price: float
    qty: float
    fee_usd: float
    order_id: str | None = None


class Broker(Protocol):
    async def buy(self, symbol: str, qty: float, ref_price: float) -> Fill: ...
    async def sell(self, symbol: str, qty: float, ref_price: float) -> Fill: ...


class PaperBroker:
    """Simula la ejecución al precio de referencia con slippage y comisión."""

    def __init__(self, fee_pct: float = 0.1, slippage_pct: float = 0.05):
        self.fee, self.slip = fee_pct / 100, slippage_pct / 100

    async def buy(self, symbol: str, qty: float, ref_price: float) -> Fill:
        price = ref_price * (1 + self.slip)
        return Fill(price, qty, price * qty * self.fee)

    async def sell(self, symbol: str, qty: float, ref_price: float) -> Fill:
        price = ref_price * (1 - self.slip)
        return Fill(price, qty, price * qty * self.fee)


class LiveBroker:
    """Órdenes de mercado reales en Binance spot vía ccxt."""

    def __init__(self, api_key: str, secret: str, exchange_id: str = "binance"):
        self.ex = getattr(ccxt, exchange_id)({"apiKey": api_key, "secret": secret, "enableRateLimit": True})

    async def close(self) -> None:
        await self.ex.close()

    async def _fill(self, order: dict, symbol: str, ref_price: float) -> Fill:
        price = float(order.get("average") or order.get("price") or ref_price)
        qty = float(order.get("filled") or order.get("amount") or 0)
        fee = 0.0
        for f in order.get("fees") or ([order["fee"]] if order.get("fee") else []):
            if not f or f.get("cost") is None:
                continue
            cost = float(f["cost"])
            fee += cost if f.get("currency") == symbol.split("/")[1] else cost * price
        return Fill(price, qty, fee, str(order.get("id")))

    async def buy(self, symbol: str, qty: float, ref_price: float) -> Fill:
        await self.ex.load_markets()
        amount = float(self.ex.amount_to_precision(symbol, qty))
        order = await self.ex.create_order(symbol, "market", "buy", amount)
        log.warning("ORDEN REAL compra %s %s → %s", symbol, amount, order.get("id"))
        return await self._fill(order, symbol, ref_price)

    async def sell(self, symbol: str, qty: float, ref_price: float) -> Fill:
        await self.ex.load_markets()
        base = symbol.split("/")[0]
        bal = await self.ex.fetch_balance()
        free = float(bal.get(base, {}).get("free") or 0)
        amount = float(self.ex.amount_to_precision(symbol, min(qty, free)))  # la comisión puede descontarse del activo
        order = await self.ex.create_order(symbol, "market", "sell", amount)
        log.warning("ORDEN REAL venta %s %s → %s", symbol, amount, order.get("id"))
        return await self._fill(order, symbol, ref_price)


class CcxtPriceSource:
    """Último precio spot (público) para el monitor de posiciones. Una sola instancia: los
    mercados se cargan una vez y no en cada consulta."""

    def __init__(self, exchange_id: str = "binance"):
        self.ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})

    async def __call__(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        tickers = await self.ex.fetch_tickers(symbols)
        return {s: float(t["last"]) for s, t in tickers.items() if t.get("last")}

    async def close(self) -> None:
        await self.ex.close()
