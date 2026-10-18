"""Acceso a datos de mercado vía ccxt (async).

Se usa la API unificada de ccxt para todo lo estándar (tickers, OHLCV, funding, OI)
y los endpoints "implícitos" de Binance sólo para lo que la API unificada no expone:
volumen comprador taker por vela (para CVD) y ratios long/short.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

import ccxt.async_support as ccxt
import pandas as pd

from ..config import AgentConfig

log = logging.getLogger(__name__)

RETRYABLE = (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout, ccxt.RateLimitExceeded)

TF_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
    "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000, "1d": 86_400_000,
}  # fmt: skip


def perp_symbol(spot_symbol: str) -> str:
    base, quote = spot_symbol.split("/")
    return f"{base}/{quote}:{quote}"


def _klines_to_df(rows: list[list[Any]], timeframe: str, drop_open_candle: bool = True) -> pd.DataFrame:
    """Klines crudos de Binance → DataFrame con taker_buy_volume."""
    df = pd.DataFrame(
        [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[9])] for r in rows],
        columns=["ts", "open", "high", "low", "close", "volume", "taker_buy_volume"],
    )
    return _finalize(df, timeframe, drop_open_candle)


def _finalize(df: pd.DataFrame, timeframe: str, drop_open_candle: bool) -> pd.DataFrame:
    if drop_open_candle and len(df) and df["ts"].iloc[-1] + TF_MS.get(timeframe, 0) > time.time() * 1000:
        df = df.iloc[:-1]  # la vela en curso todavía no cerró: no se analiza
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    return df


class MarketData:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        opts = {"enableRateLimit": True, "timeout": 20_000}
        self.spot = getattr(ccxt, cfg.exchange.spot)(dict(opts))
        self.deriv = getattr(ccxt, cfg.exchange.derivatives)(dict(opts))
        self.sem = asyncio.Semaphore(cfg.concurrency)
        self._loaded = False

    async def __aenter__(self) -> "MarketData":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await asyncio.gather(self.spot.close(), self.deriv.close(), return_exceptions=True)

    async def load(self) -> None:
        if not self._loaded:
            await asyncio.gather(self.spot.load_markets(), self.deriv.load_markets())
            self._loaded = True

    async def call(self, fn: Callable[..., Awaitable[Any]], *args, retries: int = 3, **kwargs) -> Any:
        delay = 2.0
        for attempt in range(retries + 1):
            try:
                async with self.sem:
                    return await fn(*args, **kwargs)
            except RETRYABLE as exc:
                if attempt == retries:
                    raise
                log.debug("reintento %s/%s %s: %s", attempt + 1, retries, getattr(fn, "__name__", fn), exc)
                await asyncio.sleep(delay)
                delay *= 2

    @property
    def is_binance(self) -> bool:
        return self.spot.id.startswith("binance") and self.deriv.id.startswith("binance")

    async def candles(self, symbol: str, timeframe: str, limit: int, market: str = "spot") -> pd.DataFrame:
        """OHLCV cerrado. En Binance incluye `taker_buy_volume` (necesario para el CVD)."""
        await self.load()
        ex = self.spot if market == "spot" else self.deriv
        sym = symbol if market == "spot" else perp_symbol(symbol)
        if self.is_binance:
            mid = ex.market(sym)["id"]
            params = {"symbol": mid, "interval": timeframe, "limit": min(limit + 1, 1000)}
            raw = ex.publicGetKlines if market == "spot" else ex.fapiPublicGetKlines
            rows = await self.call(raw, params)
            return _klines_to_df(rows, timeframe)
        rows = await self.call(ex.fetch_ohlcv, sym, timeframe, None, limit + 1)
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        return _finalize(df, timeframe, True)

    async def history(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        """Historial largo paginado (para backtesting)."""
        await self.load()
        since = int((time.time() - days * 86400) * 1000)
        frames = []
        while True:
            rows = await self.call(self.spot.fetch_ohlcv, symbol, timeframe, since, 1000)
            if not rows:
                break
            frames.append(pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]))
            since = rows[-1][0] + TF_MS[timeframe]
            if len(rows) < 1000 or since > time.time() * 1000:
                break
        if not frames:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.concat(frames).drop_duplicates("ts")
        return _finalize(df, timeframe, True)

    async def universe(self) -> list[str]:
        """Top N por volumen en perpetuos que además tienen par spot (precio y CVD spot)."""
        await self.load()
        u = self.cfg.universe
        q = self.cfg.exchange.quote
        tickers = await self.call(self.deriv.fetch_tickers)
        rows = []
        for sym, t in tickers.items():
            m = self.deriv.markets.get(sym)
            if not m or not m.get("swap") or not m.get("linear") or m.get("quote") != q or not m.get("active", True):
                continue
            base = m["base"]
            spot_sym = f"{base}/{q}"
            if base in u.exclude_bases or spot_sym not in self.spot.markets:
                continue
            qv = t.get("quoteVolume") or 0
            if qv >= u.min_quote_volume_usd:
                rows.append((spot_sym, qv))
        rows.sort(key=lambda x: -x[1])
        top = [s for s, _ in rows[: u.top_n]]
        for s in u.always_include:
            if s not in top and s in self.spot.markets:
                top.append(s)
        return top
