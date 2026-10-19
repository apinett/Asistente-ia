"""CLI del agente.

  python -m cryptoagent serve                 # API + escaneos continuos (modo VPS)
  python -m cryptoagent scan [-s BTC/USDT]    # un escaneo completo y muestra el ranking
  python -m cryptoagent report                # genera y envía el informe diario ahora
  python -m cryptoagent evaluate              # evalúa señales pasadas y recalibra pesos
  python -m cryptoagent backtest -s BTC/USDT -t 4h -d 730
  python -m cryptoagent doctor                # verifica conexiones y configuración (post-despliegue)
"""

from __future__ import annotations

import argparse
import asyncio
import json

from .config import get_config, get_secrets
from .logging_setup import setup_logging


def _print_ranking(analyses) -> None:
    from .agent.serialize import fmt_price

    print(f"\n{'Símbolo':<14}{'Precio':>14}{'Score':>8}{'Conf':>6}  {'Señal':<16}{'LPF':>6}  Claves")
    for a in sorted(analyses, key=lambda x: x.score, reverse=True):
        lpf = f"{a.positioning.score:+.2f}" if a.positioning else "  -  "
        key = a.highlights[0] if a.highlights else ""
        print(f"{a.symbol:<14}{fmt_price(a.price):>14}{a.score:>+8.0f}{a.confidence:>6.2f}  {a.label:<16}{lpf:>6}  {key}")


async def _scan(symbols: list[str] | None) -> None:
    from .agent.orchestrator import CryptoAgent

    agent = CryptoAgent(get_config(), get_secrets())
    _print_ranking(await agent.scan("full", symbols))
    if agent.market_regime:
        print("\nRégimen de mercado:", agent.market_regime)
    if agent.breadth:
        print("Amplitud:", json.dumps(agent.breadth, ensure_ascii=False))


async def _report() -> None:
    from .agent.orchestrator import CryptoAgent

    print(await CryptoAgent(get_config(), get_secrets()).daily_report())


async def _evaluate() -> None:
    from .agent.orchestrator import CryptoAgent

    print("evaluadas:", await CryptoAgent(get_config(), get_secrets()).evaluate())


async def _backtest(symbol: str, timeframe: str, days: int, horizon: int) -> None:
    from .agent.backtest import run_backtest, summarize
    from .market.exchange import MarketData

    cfg = get_config()
    async with MarketData(cfg) as md:
        df = await md.history(symbol, timeframe, days)
    print(f"{symbol} {timeframe}: {len(df)} velas, horizonte {horizon} velas")
    res = await asyncio.to_thread(run_backtest, df, timeframe, cfg.scoring.weights, horizon)
    print(summarize(res).to_string(index=False))


async def _doctor() -> bool:
    """Chequeo de punta a punta de la instalación. Devuelve False si falla algo crítico."""
    from .market.derivatives import fetch_derivatives
    from .market.exchange import MarketData
    from .market.macro import fetch_macro
    from .notify.telegram import Telegram
    from .storage.db import Database

    cfg, sec = get_config(), get_secrets()
    ok_all = True

    def line(ok: bool | None, what: str, detail: str = "", critical: bool = False) -> None:
        nonlocal ok_all
        mark = {True: "✔", False: "✖", None: "–"}[ok]
        print(f"  {mark} {what}" + (f": {detail}" if detail else ""))
        if ok is False and critical:
            ok_all = False

    print("Crypto Agent · diagnóstico\n")
    line(True, "Configuración", f"{sec.config_path} · universo top {cfg.universe.top_n} · trading '{cfg.trading.mode}'")
    try:
        db = Database(sec.database_url)
        db.set_kv("doctor", "ok")
        line(db.get_kv("doctor") == "ok", "Base de datos", sec.database_url, critical=True)
    except Exception as exc:
        line(False, "Base de datos", str(exc), critical=True)

    async with MarketData(cfg) as md:
        try:
            df = await md.candles("BTC/USDT", "1h", 5)
            line(len(df) > 0, f"Exchange spot ({cfg.exchange.spot})", f"BTC/USDT {df['close'].iloc[-1]:,.2f}", critical=True)
        except Exception as exc:
            line(False, f"Exchange spot ({cfg.exchange.spot})", str(exc)[:200], critical=True)
        try:
            dd = await fetch_derivatives(md, "BTC/USDT", cfg.positioning.period)
            parts = {
                "OI": dd is not None and dd.open_interest is not None,
                "funding": dd is not None and dd.funding is not None,
                "L/S": dd is not None and dd.top_ls_ratio is not None,
                "CVD": dd is not None and dd.spot is not None and "taker_buy_volume" in dd.spot,
            }
            line(all(parts.values()), f"Derivados LPF ({cfg.exchange.derivatives})", " · ".join(f"{k} {'ok' if v else 'NO'}" for k, v in parts.items()))
        except Exception as exc:
            line(False, "Derivados LPF", str(exc)[:200])

    macro = await fetch_macro()
    line(bool(macro), "Datos macro", ", ".join(macro) or "sin respuesta")

    tg = Telegram(sec.telegram_bot_token, sec.telegram_chat_id)
    if tg.enabled:
        line(await tg.send("✅ Crypto Agent: prueba de conexión desde el VPS."), "Telegram", "mensaje de prueba enviado")
    else:
        line(None, "Telegram", "no configurado (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")

    if sec.anthropic_api_key:
        try:
            import anthropic

            m = await anthropic.AsyncAnthropic(api_key=sec.anthropic_api_key).models.retrieve(sec.claude_model)
            line(True, "Claude", m.id)
        except Exception as exc:
            line(False, "Claude", str(exc)[:200])
    else:
        line(None, "Claude", "sin ANTHROPIC_API_KEY: el informe usa plantilla")

    line(bool(sec.api_token), "API_TOKEN", "configurado" if sec.api_token else "falta: el dashboard no va a funcionar", critical=True)

    if sec.binance_api_key and sec.binance_api_secret:
        from .trading.brokers import LiveBroker

        lb = LiveBroker(sec.binance_api_key, sec.binance_api_secret, cfg.exchange.spot)
        try:
            bal = await lb.ex.fetch_balance()
            usdt = bal.get("USDT", {}).get("free")
            line(True, "API key de Binance (trading)", f"USDT libre {usdt} · trading real {'HABILITADO' if sec.trading_live_enabled else 'deshabilitado'}")
        except Exception as exc:
            line(False, "API key de Binance (trading)", str(exc)[:200])
        finally:
            await lb.close()
    else:
        line(None, "API key de Binance (trading)", "no cargada: sólo modos pausado y simulado")

    print("\nResultado:", "OK" if ok_all else "HAY ERRORES CRÍTICOS")
    return ok_all


def main() -> None:
    ap = argparse.ArgumentParser(prog="cryptoagent")
    sub = ap.add_subparsers(dest="cmd")
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("-s", "--symbols", nargs="*")
    sub.add_parser("report")
    sub.add_parser("evaluate")
    sub.add_parser("doctor")
    p_bt = sub.add_parser("backtest")
    p_bt.add_argument("-s", "--symbol", default="BTC/USDT")
    p_bt.add_argument("-t", "--timeframe", default="4h")
    p_bt.add_argument("-d", "--days", type=int, default=730)
    p_bt.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()

    setup_logging(get_secrets().log_level)
    cmd = args.cmd or "serve"
    if cmd == "serve":
        import uvicorn

        uvicorn.run(
            "cryptoagent.api.server:app",
            host=getattr(args, "host", "0.0.0.0"),
            port=getattr(args, "port", 8000),
            proxy_headers=True,
            log_level="info",
        )
    elif cmd == "scan":
        asyncio.run(_scan(args.symbols))
    elif cmd == "report":
        asyncio.run(_report())
    elif cmd == "evaluate":
        asyncio.run(_evaluate())
    elif cmd == "doctor":
        raise SystemExit(0 if asyncio.run(_doctor()) else 1)
    elif cmd == "backtest":
        asyncio.run(_backtest(args.symbol, args.timeframe, args.days, args.horizon))


if __name__ == "__main__":
    main()
