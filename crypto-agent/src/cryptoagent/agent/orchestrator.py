"""Orquestador: escaneo del universo, persistencia, alertas e informe diario."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from ..analysis.indicators import compute_indicators
from ..analysis.positioning import analyze_positioning
from ..analysis.regime import hmm_market_regime
from ..analysis.relative import market_breadth, relative_strength
from ..analysis.scoring import SymbolAnalysis, analyze_timeframe, combine
from ..config import AgentConfig, Secrets
from ..market.derivatives import fetch_derivatives
from ..market.exchange import MarketData
from ..market.macro import fetch_macro
from ..notify.telegram import Telegram
from ..storage.db import Database, Report, Signal, utcnow
from ..trading.brokers import CcxtPriceSource
from ..trading.engine import TradingEngine
from .evaluation import evaluate_signals, performance_summary
from .llm import write_narrative
from .report import build_context, template_report
from .serialize import alert_text, analysis_to_dict

log = logging.getLogger(__name__)
MIN_BARS = 60
FAST_TIMEFRAMES = ("1h", "15m")
FAST_TOP = 15


class CryptoAgent:
    def __init__(
        self, cfg: AgentConfig, secrets: Secrets, db: Database | None = None, md_factory=MarketData, prices=None
    ):
        self.cfg = cfg
        self.secrets = secrets
        self.db = db or Database(secrets.database_url)
        self.md_factory = md_factory
        self.telegram = Telegram(secrets.telegram_bot_token, secrets.telegram_chat_id)
        self._universe: list[str] = []
        self._universe_ts = 0.0
        self.latest: dict[str, SymbolAnalysis] = {}
        self.latest_ts: dt.datetime | None = None
        self._daily: dict[str, pd.DataFrame] = {}
        self.breadth: dict = {}
        self.market_regime: dict | None = None
        self._lock = asyncio.Lock()
        self.trader = TradingEngine(
            cfg, secrets, self.db, prices or CcxtPriceSource(cfg.exchange.spot), notify=self.telegram.send
        )

    # ------------------------------------------------------------------ análisis
    async def universe(self, md: MarketData) -> list[str]:
        if not self._universe or time.time() - self._universe_ts > 6 * 3600:
            self._universe = await md.universe()
            self._universe_ts = time.time()
            log.info("universo: %d activos", len(self._universe))
        return self._universe

    def _analyze_frames(self, frames: dict[str, pd.DataFrame]):
        """Parte CPU (TA-Lib): se ejecuta en un thread para no bloquear el event loop."""
        out = {}
        for tf, df in frames.items():
            if df is not None and len(df) >= MIN_BARS:
                ind = compute_indicators(df)
                out[tf] = (analyze_timeframe(ind, tf), ind)
        return out

    async def analyze_symbol(
        self,
        md: MarketData,
        symbol: str,
        timeframes: tuple[str, ...],
        btc_daily: pd.DataFrame | None = None,
        with_positioning: bool = True,
    ) -> SymbolAnalysis | None:
        cfg = self.cfg
        dfs = await asyncio.gather(*(md.candles(symbol, tf, cfg.candles_limit) for tf in timeframes), return_exceptions=True)
        frames = {tf: df for tf, df in zip(timeframes, dfs) if not isinstance(df, BaseException)}
        for tf, df in zip(timeframes, dfs):
            if isinstance(df, BaseException):
                log.info("%s %s sin velas: %s", symbol, tf, df)
        analyzed = await asyncio.to_thread(self._analyze_frames, frames)
        if not analyzed:
            return None
        tfs = {tf: a for tf, (a, _) in analyzed.items()}
        if "1d" in analyzed:
            self._daily[symbol] = analyzed["1d"][1].tail(10)

        primary = tfs.get(cfg.primary_timeframe) or next(iter(tfs.values()))
        positioning = None
        if with_positioning and cfg.positioning.enabled:
            dd = await fetch_derivatives(md, symbol, cfg.positioning.period)
            if dd is not None:
                mom_sign = float(np.sign(primary.momentum.score + primary.trend))
                positioning = analyze_positioning(dd, cfg.positioning.lookback_bars, cfg.positioning.leverage_tiers, mom_sign)

        rs = None
        if btc_daily is not None and "1d" in analyzed and symbol != "BTC/USDT":
            rs = relative_strength(analyzed["1d"][1]["close"], btc_daily["close"])

        tf_weights = {tf: w for tf, w in cfg.timeframes.items() if tf in timeframes}
        adaptive = self.db.adaptive_weights() if cfg.scoring.adaptive_weights else {}
        return combine(
            symbol,
            tfs,
            tf_weights,
            cfg.scoring.weights,
            cfg.primary_timeframe if cfg.primary_timeframe in tfs else next(iter(tfs)),
            positioning=positioning,
            rel_strength=rs,
            adaptive=adaptive,
            strong=cfg.scoring.strong_threshold,
            signal=cfg.scoring.signal_threshold,
        )

    async def scan(self, kind: str = "full", symbols: list[str] | None = None) -> list[SymbolAnalysis]:
        """kind="full": todas las temporalidades + LPF. kind="fast": timing intradía sobre el top 15."""
        async with self._lock:
            t0 = time.time()
            async with self.md_factory(self.cfg) as md:
                universe = symbols or await self.universe(md)
                timeframes = tuple(self.cfg.timeframes)
                if kind == "fast":
                    universe = universe[:FAST_TOP]
                    timeframes = tuple(tf for tf in FAST_TIMEFRAMES if tf in self.cfg.timeframes) or timeframes

                btc_daily = None
                if kind == "full":
                    btc_daily = await md.candles("BTC/USDT", "1d", 1000)
                    reg = await asyncio.to_thread(hmm_market_regime, btc_daily)
                    self.market_regime = asdict(reg) if reg else None

                results = await asyncio.gather(
                    *(self.analyze_symbol(md, s, timeframes, btc_daily) for s in universe), return_exceptions=True
                )
            analyses: list[SymbolAnalysis] = []
            for sym, r in zip(universe, results):
                if isinstance(r, BaseException):
                    log.warning("%s falló: %r", sym, r)
                elif r is not None:
                    analyses.append(r)

            if kind == "full":
                self.latest = {a.symbol: a for a in analyses}
                self.latest_ts = utcnow()
                self.breadth = market_breadth({a.symbol: self._daily[a.symbol] for a in analyses if a.symbol in self._daily})
            await self._persist_and_alert(analyses, kind)
            if kind == "full":
                try:
                    await self.trader.on_scan(analyses)
                except Exception:  # el trading nunca debe tumbar el análisis
                    log.exception("módulo de trading falló")
            log.info("escaneo %s: %d activos en %.1fs", kind, len(analyses), time.time() - t0)
            return analyses

    # ------------------------------------------------------------- persistencia
    async def _persist_and_alert(self, analyses: list[SymbolAnalysis], kind: str) -> None:
        cfg = self.cfg
        to_alert: list[tuple[SymbolAnalysis, str]] = []
        now = utcnow()
        with self.db.session() as s:
            for a in analyses:
                sig = Signal(
                    kind=kind,
                    symbol=a.symbol,
                    price=a.price,
                    score=a.score,
                    label=a.label,
                    confidence=a.confidence,
                    components=a.components,
                    plan=asdict(a.plan) if a.plan else None,
                    details=analysis_to_dict(a, detail=kind == "full"),
                )
                if self._should_alert(a, kind, now):
                    sig.alerted = True
                    prefix = "⏱️ Timing intradía · " if kind == "fast" else ""
                    to_alert.append((a, prefix))
                s.add(sig)
            s.commit()
        to_alert.sort(key=lambda x: abs(x[0].score) * x[0].confidence, reverse=True)
        for a, prefix in to_alert[: cfg.alerts.max_per_scan]:
            await self.telegram.send(alert_text(a, cfg.primary_timeframe, prefix))

    def _should_alert(self, a: SymbolAnalysis, kind: str, now: dt.datetime) -> bool:
        al = self.cfg.alerts
        if abs(a.score) < al.min_abs_score:
            return False
        if kind == "fast":
            # El escaneo rápido sólo alerta si coincide con el sesgo del último escaneo completo
            base = self.db.last_signal(a.symbol, "full")
            if base is None or np.sign(base.score) != np.sign(a.score) or abs(base.score) < self.cfg.scoring.signal_threshold:
                return False
        last = self.db.last_alert(a.symbol)
        if last is None:
            return True
        last_ts = last.ts if last.ts.tzinfo else last.ts.replace(tzinfo=dt.timezone.utc)
        same_side = np.sign(last.score) == np.sign(a.score)
        return not same_side or (now - last_ts) > dt.timedelta(hours=al.cooldown_hours)

    # ------------------------------------------------------------------ informe
    async def daily_report(self) -> str:
        stale = self.latest_ts is None or utcnow() - self.latest_ts > dt.timedelta(hours=2)
        if stale:
            await self.scan("full")
        analyses = list(self.latest.values())
        macro = await fetch_macro()
        ctx = build_context(analyses, self.breadth, macro, self.market_regime, performance_summary(self.db))
        text = await write_narrative(ctx, self.secrets.anthropic_api_key, self.secrets.claude_model)
        content = text or template_report(ctx)
        with self.db.session() as s:
            s.add(Report(kind="daily", content=content, context=ctx))
            s.commit()
        await self.telegram.send(content)
        return content

    async def evaluate(self) -> int:
        async with self.md_factory(self.cfg) as md:
            return await evaluate_signals(self.db, md)
