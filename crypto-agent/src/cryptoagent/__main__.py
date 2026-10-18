"""CLI del agente.

  python -m cryptoagent serve                 # API + escaneos continuos (modo VPS)
  python -m cryptoagent scan [-s BTC/USDT]    # un escaneo completo y muestra el ranking
  python -m cryptoagent report                # genera y envía el informe diario ahora
  python -m cryptoagent evaluate              # evalúa señales pasadas y recalibra pesos
  python -m cryptoagent backtest -s BTC/USDT -t 4h -d 730
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
    elif cmd == "backtest":
        asyncio.run(_backtest(args.symbol, args.timeframe, args.days, args.horizon))


if __name__ == "__main__":
    main()
