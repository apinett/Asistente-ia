"""Motor de trading: decide entradas/salidas a partir de las señales y gestiona el riesgo.

Modos
  paused  no abre posiciones (por defecto). Si quedaron posiciones abiertas, sus stops/objetivos
          se siguen gestionando para no dejarlas desprotegidas.
  paper   simulado con saldo virtual: mismo circuito que el real, sin tocar el exchange.
  live    órdenes reales en Binance spot. Requiere TODAS las compuertas de `live_gates()`.

Reglas (sólo largos en spot, sin apalancamiento)
  Entrada  señal ALCISTA con score ≥ min_score, confianza ≥ min_confidence, R:R ≥ min_risk_reward.
  Tamaño   se arriesga risk_per_trade_pct del capital entre entrada y stop, con tope de
           max_position_pct del capital por posición y max_open_positions simultáneas.
  Salida   stop, objetivo 1, señal contraria (score ≤ −umbral), o tiempo máximo.
  Kill     si la pérdida del día supera daily_loss_limit_pct, el motor se pausa solo
           (y opcionalmente cierra todo) y avisa por Telegram.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import asdict

from sqlalchemy import select

from ..analysis.scoring import SymbolAnalysis
from ..config import AgentConfig, Secrets
from ..storage.db import Database, Trade, utcnow
from .brokers import Broker, LiveBroker, PaperBroker, PriceSource
from .readiness import compute_readiness, qualifies

log = logging.getLogger(__name__)
MODES = ("paused", "paper", "live")


def _aware(ts: dt.datetime) -> dt.datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)


class TradingEngine:
    def __init__(
        self,
        cfg: AgentConfig,
        secrets: Secrets,
        db: Database,
        prices: PriceSource,
        notify=None,
        live_broker_factory=None,
    ):
        self.cfg, self.secrets, self.db, self.prices = cfg, secrets, db, prices
        self.notify = notify
        self.paper_broker = PaperBroker(cfg.trading.fee_pct, cfg.trading.slippage_pct)
        self._live_factory = live_broker_factory or (
            lambda: LiveBroker(secrets.binance_api_key, secrets.binance_api_secret, cfg.exchange.spot)
        )

    # ------------------------------------------------------------------ modo
    def desired_mode(self) -> str:
        mode = self.db.get_kv("trading_mode", self.cfg.trading.mode)
        return mode if mode in MODES else "paused"

    def live_gates(self) -> list[dict]:
        rd = compute_readiness(self.db, self.cfg)
        gates = [
            {"label": "TRADING_LIVE_ENABLED=true en el entorno", "ok": self.secrets.trading_live_enabled},
            {"label": "API key y secret de Binance cargadas", "ok": bool(self.secrets.binance_api_key and self.secrets.binance_api_secret)},
            {
                "label": f"Nivel de confianza completo ({rd['level_pct']}%)",
                "ok": rd["ready_for_live"] or not self.cfg.trading.require_readiness_for_live,
            },
        ]  # fmt: skip
        return gates

    def effective_mode(self) -> str:
        mode = self.desired_mode()
        if mode == "live" and not all(g["ok"] for g in self.live_gates()):
            return "paused"
        return mode

    async def set_mode(
        self, mode: str, reason: str = "dashboard", close_all: bool = False, close_modes: tuple[str, ...] = ("paper", "live")
    ) -> tuple[bool, str]:
        if mode not in MODES:
            return False, f"modo inválido: {mode}"
        if mode == "live":
            missing = [g["label"] for g in self.live_gates() if not g["ok"]]
            if missing:
                return False, "No se puede activar el modo real. Falta: " + "; ".join(missing)
        prev = self.desired_mode()
        self.db.set_kv("trading_mode", mode)
        self.db.set_kv("trading_mode_reason", {"reason": reason, "ts": utcnow().isoformat(), "from": prev})
        if close_all:
            await self.close_all(reason, close_modes)
        msg = f"Trading: {prev} → {mode} ({reason})"
        log.warning(msg)
        if self.notify and prev != mode:
            await self.notify(f"⚙️ {msg}")
        return True, msg

    # ---------------------------------------------------------------- cuenta
    def _trades(self, mode: str, status: str | None = None) -> list[Trade]:
        with self.db.session() as s:
            q = select(Trade).where(Trade.mode == mode)
            if status:
                q = q.where(Trade.status == status)
            return list(s.scalars(q.order_by(Trade.entry_ts)))

    def capital(self, mode: str) -> float:
        return self.cfg.trading.paper_starting_balance if mode == "paper" else self.cfg.trading.live_capital_usd

    def account(self, mode: str, prices: dict[str, float] | None = None) -> dict:
        prices = prices or {}
        closed = self._trades(mode, "closed")
        open_ = self._trades(mode, "open")
        realized = sum(t.pnl_usd or 0 for t in closed)
        invested = sum(t.entry_price * t.qty + t.fees_usd for t in open_)
        unrealized = sum((prices.get(t.symbol, t.entry_price) - t.entry_price) * t.qty - t.fees_usd for t in open_)
        start = self.capital(mode)
        cash = start + realized - invested
        equity = start + realized + unrealized
        wins = [t for t in closed if (t.pnl_usd or 0) > 0]
        losses = [t for t in closed if (t.pnl_usd or 0) < 0]
        gl = -sum(t.pnl_usd for t in losses)
        return {
            "mode": mode,
            "start_capital": start,
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "return_pct": round((equity / start - 1) * 100, 2) if start else 0.0,
            "open_positions": len(open_),
            "closed_trades": len(closed),
            "win_rate": round(len(wins) / len(closed), 4) if closed else None,
            "profit_factor": round(sum(t.pnl_usd for t in wins) / gl, 2) if gl > 0 else None,
            "avg_r": round(sum(t.r_multiple or 0 for t in closed) / len(closed), 3) if closed else None,
        }

    def equity_curve(self, mode: str) -> list[dict]:
        eq = self.capital(mode)
        pts = []
        for t in self._trades(mode, "closed"):
            eq += t.pnl_usd or 0
            pts.append({"ts": _aware(t.exit_ts).isoformat(), "equity": round(eq, 2)})
        return pts

    def _broker(self, mode: str) -> Broker:
        return self.paper_broker if mode == "paper" else self._live_factory()

    # ------------------------------------------------------------- operación
    async def on_scan(self, analyses: list[SymbolAnalysis]) -> list[Trade]:
        """Tras cada escaneo completo: salidas por señal contraria y nuevas entradas."""
        mode = self.effective_mode()
        if mode == "paused":
            return []
        t = self.cfg.trading
        by_symbol = {a.symbol: a for a in analyses}
        thr = self.cfg.scoring.signal_threshold

        for tr in self._trades(mode, "open"):
            a = by_symbol.get(tr.symbol)
            if a is not None and a.score <= -thr:
                await self._close(tr, a.price, "señal_contraria")

        opened: list[Trade] = []
        open_syms = {x.symbol for x in self._trades(mode, "open")}
        candidates = sorted(
            (
                a
                for a in analyses
                if a.plan is not None
                and qualifies(a.score, a.confidence, asdict(a.plan), self.cfg)
                and a.symbol not in open_syms
                and (not t.allowed_symbols or a.symbol in t.allowed_symbols)
            ),
            key=lambda a: a.score * a.confidence,
            reverse=True,
        )
        for a in candidates:
            if len(open_syms) >= t.max_open_positions:
                break
            tr = await self._open(mode, a)
            if tr is not None:
                opened.append(tr)
                open_syms.add(a.symbol)
        return opened

    def _size(self, mode: str, entry: float, stop: float) -> float:
        t = self.cfg.trading
        acc = self.account(mode)
        per_unit = entry - stop
        if per_unit <= 0:
            return 0.0
        qty = acc["equity"] * t.risk_per_trade_pct / 100 / per_unit
        cap = min(acc["equity"] * t.max_position_pct / 100, acc["cash"] * 0.98)
        if qty * entry > cap:
            qty = cap / entry
        return qty if qty * entry >= t.min_notional_usd else 0.0

    async def _open(self, mode: str, a: SymbolAnalysis) -> Trade | None:
        plan = a.plan
        qty = self._size(mode, a.price, plan.stop)
        if qty <= 0:
            log.info("trading %s: %s sin capital/tamaño suficiente", mode, a.symbol)
            return None
        broker = self._broker(mode)
        try:
            fill = await broker.buy(a.symbol, qty, a.price)
        except Exception as exc:
            log.error("trading %s: fallo al comprar %s: %s", mode, a.symbol, exc)
            if self.notify:
                await self.notify(f"❌ Error al comprar {a.symbol} ({mode}): {exc}")
            return None
        finally:
            if hasattr(broker, "close"):
                await broker.close()
        tr = Trade(
            mode=mode,
            symbol=a.symbol,
            entry_price=fill.price,
            qty=fill.qty,
            stop=plan.stop,
            target=plan.targets[0],
            risk_usd=(fill.price - plan.stop) * fill.qty,
            fees_usd=fill.fee_usd,
            signal_score=a.score,
            signal_confidence=a.confidence,
            order_ids={"entry": fill.order_id},
        )
        with self.db.session() as s:
            s.add(tr)
            s.commit()
        if self.notify:
            tag = "🧪 SIMULADO" if mode == "paper" else "💰 REAL"
            await self.notify(
                f"{tag} · COMPRA {a.symbol}\nPrecio {fill.price:.6g} · cantidad {fill.qty:.6g} "
                f"(≈ {fill.price * fill.qty:,.2f} USDT)\nStop {plan.stop:.6g} · objetivo {plan.targets[0]:.6g} · "
                f"riesgo {tr.risk_usd:,.2f} USDT\nScore {a.score:+.0f} · confianza {a.confidence:.2f}"
            )
        return tr

    async def _close(self, tr: Trade, ref_price: float, reason: str) -> Trade:
        broker = self._broker(tr.mode)
        try:
            fill = await broker.sell(tr.symbol, tr.qty, ref_price)
        except Exception as exc:
            log.error("trading %s: fallo al vender %s: %s", tr.mode, tr.symbol, exc)
            first_error = not (tr.order_ids or {}).get("exit_error")
            with self.db.session() as s:
                tr = s.merge(tr)
                tr.order_ids = {**(tr.order_ids or {}), "exit_error": str(exc)[:200]}
                s.commit()
            if self.notify and first_error:  # avisar una vez; el monitor reintenta cada minuto
                await self.notify(f"❌ Error al vender {tr.symbol} ({tr.mode}): {exc}. Revisar en el exchange.")
            return tr
        finally:
            if hasattr(broker, "close"):
                await broker.close()
        with self.db.session() as s:
            tr = s.merge(tr)
            tr.status = "closed"
            tr.exit_ts = utcnow()
            tr.exit_price = fill.price
            tr.exit_reason = reason
            tr.fees_usd += fill.fee_usd
            tr.pnl_usd = (fill.price - tr.entry_price) * tr.qty - tr.fees_usd
            tr.r_multiple = tr.pnl_usd / tr.risk_usd if tr.risk_usd > 0 else None
            tr.order_ids = {**(tr.order_ids or {}), "exit": fill.order_id}
            s.commit()
        if self.notify:
            tag = "🧪 SIMULADO" if tr.mode == "paper" else "💰 REAL"
            icon = "✅" if tr.pnl_usd >= 0 else "🔻"
            await self.notify(
                f"{tag} · {icon} VENTA {tr.symbol} ({reason.replace('_', ' ')})\n"
                f"Salida {fill.price:.6g} · resultado {tr.pnl_usd:+,.2f} USDT ({tr.r_multiple or 0:+.2f} R)"
            )
        return tr

    async def close_all(self, reason: str, modes: tuple[str, ...] = ("paper", "live")) -> int:
        n = 0
        for mode in modes:
            open_ = self._trades(mode, "open")
            if not open_:
                continue
            px = await self.prices([t.symbol for t in open_])
            for tr in open_:
                await self._close(tr, px.get(tr.symbol, tr.entry_price), reason)
                n += 1
        return n

    async def monitor(self) -> None:
        """Cada minuto: stops, objetivos, tiempo máximo y kill switch diario."""
        now = utcnow()
        for mode in ("paper", "live"):
            open_ = self._trades(mode, "open")
            if not open_:
                continue
            px = await self.prices(sorted({t.symbol for t in open_}))
            for tr in open_:
                p = px.get(tr.symbol)
                if p is None:
                    continue
                if p <= tr.stop:
                    await self._close(tr, p, "stop")
                elif p >= tr.target:
                    await self._close(tr, p, "objetivo")
                elif (now - _aware(tr.entry_ts)).total_seconds() / 3600 >= self.cfg.trading.max_hold_hours:
                    await self._close(tr, p, "tiempo")
            await self._kill_switch(mode, px)

    async def _kill_switch(self, mode: str, prices: dict[str, float]) -> None:
        if self.desired_mode() != mode:
            return
        start_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        realized_today = sum(
            t.pnl_usd or 0 for t in self._trades(mode, "closed") if t.exit_ts and _aware(t.exit_ts) >= start_day
        )
        unrealized = sum((prices.get(t.symbol, t.entry_price) - t.entry_price) * t.qty for t in self._trades(mode, "open"))
        loss_pct = -(realized_today + unrealized) / self.capital(mode) * 100
        if loss_pct >= self.cfg.trading.daily_loss_limit_pct:
            await self.set_mode(
                "paused",
                f"kill switch: pérdida diaria {loss_pct:.1f}%",
                close_all=self.cfg.trading.kill_switch_close_positions,
                close_modes=(mode,),  # una pérdida simulada nunca cierra posiciones reales (ni al revés)
            )

    def status(self, prices: dict[str, float] | None = None) -> dict:
        prices = prices or {}
        desired = self.desired_mode()
        accounts = {m: self.account(m, prices) for m in ("paper", "live")}
        open_pos = []
        for m in ("paper", "live"):
            for t in self._trades(m, "open"):
                p = prices.get(t.symbol)
                open_pos.append(
                    {
                        "id": t.id, "mode": m, "symbol": t.symbol, "entry_ts": _aware(t.entry_ts).isoformat(),
                        "entry_price": t.entry_price, "qty": t.qty, "stop": t.stop, "target": t.target, "price": p,
                        "pnl_usd": round((p - t.entry_price) * t.qty - t.fees_usd, 2) if p else None,
                    }  # fmt: skip
                )
        return {
            "desired_mode": desired,
            "effective_mode": self.effective_mode(),
            "configured_mode": self.cfg.trading.mode,
            "mode_reason": self.db.get_kv("trading_mode_reason"),
            "live_gates": self.live_gates(),
            "readiness": compute_readiness(self.db, self.cfg),
            "accounts": accounts,
            "open_positions": open_pos,
            "equity_curve": {m: self.equity_curve(m) for m in ("paper", "live")},
            "rules": self.cfg.trading.model_dump(exclude={"readiness"}),
        }

    def trades(self, limit: int = 100) -> list[dict]:
        with self.db.session() as s:
            rows = s.scalars(select(Trade).order_by(Trade.entry_ts.desc()).limit(limit))
            return [
                {
                    "id": t.id, "mode": t.mode, "symbol": t.symbol, "status": t.status,
                    "entry_ts": _aware(t.entry_ts).isoformat(), "entry_price": t.entry_price, "qty": t.qty,
                    "stop": t.stop, "target": t.target, "exit_ts": _aware(t.exit_ts).isoformat() if t.exit_ts else None,
                    "exit_price": t.exit_price, "exit_reason": t.exit_reason, "pnl_usd": t.pnl_usd, "r": t.r_multiple,
                }  # fmt: skip
                for t in rows
            ]
