"""API HTTP (FastAPI) + planificador en el mismo proceso.

Un solo contenedor: uvicorn levanta la API y, en el `lifespan`, arranca el scheduler
que ejecuta los escaneos. Coolify publica el puerto 8000 detrás de su proxy con HTTPS.
"""

from __future__ import annotations

import os
import secrets as pysecrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select

from .. import __version__
from ..agent.evaluation import performance_summary
from ..agent.orchestrator import CryptoAgent
from ..agent.serialize import analysis_to_dict
from ..agent.stats import effectiveness
from ..config import get_config, get_secrets
from ..logging_setup import setup_logging
from ..scheduler import build_scheduler
from ..storage.db import Report, Signal

bearer = HTTPBearer(auto_error=False)
STATE: dict = {}
DASHBOARD = Path(__file__).parent / "static" / "dashboard.html"


def auth(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    token = get_secrets().api_token
    if not token:
        raise HTTPException(503, "API_TOKEN no configurado")
    if cred is None or not pysecrets.compare_digest(cred.credentials, token):
        raise HTTPException(401, "token inválido")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sec = get_secrets()
    setup_logging(sec.log_level)
    agent = CryptoAgent(get_config(), sec)
    backup_dir = os.path.join(os.path.dirname(sec.database_url.removeprefix("sqlite:///")) or ".", "backups")
    sched = build_scheduler(agent, sec.tz, backup_dir)
    if os.getenv("DISABLE_SCHEDULER") != "1":
        sched.start()
    STATE.update(agent=agent, sched=sched)
    yield
    if sched.running:
        sched.shutdown(wait=False)
    close = getattr(agent.trader.prices, "close", None)
    if close:
        await close()


app = FastAPI(title="Crypto Agent", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=DASHBOARD.parent), name="static")


def agent() -> CryptoAgent:
    return STATE["agent"]


@app.get("/health")
def health():
    a = STATE.get("agent")
    sched = STATE.get("sched")
    return {
        "status": "ok",
        "version": __version__,
        "last_full_scan": a.latest_ts if a else None,
        "jobs": [{"id": j.id, "next_run": j.next_run_time} for j in sched.get_jobs()] if sched and sched.running else [],
    }


@app.get("/market", dependencies=[Depends(auth)])
def market():
    a = agent()
    ranked = sorted(a.latest.values(), key=lambda x: x.score, reverse=True)
    return {
        "ts": a.latest_ts,
        "regime": a.market_regime,
        "breadth": a.breadth,
        "signals": [analysis_to_dict(x, detail=False) for x in ranked],
    }


@app.get("/symbol/{base}", dependencies=[Depends(auth)])
def symbol(base: str, quote: str = "USDT"):
    sym = f"{base.upper()}/{quote.upper()}"
    a = agent().latest.get(sym)
    if not a:
        raise HTTPException(404, f"{sym} no está en el último escaneo")
    return analysis_to_dict(a, detail=True)


@app.post("/scan", dependencies=[Depends(auth)])
async def scan_now(symbols: list[str] | None = None):
    res = await agent().scan("full", symbols)
    return {"analyzed": len(res)}


@app.post("/report", dependencies=[Depends(auth)])
async def report_now():
    return {"report": await agent().daily_report()}


@app.get("/report/latest", dependencies=[Depends(auth)])
def report_latest():
    with agent().db.session() as s:
        r = s.scalars(select(Report).order_by(Report.ts.desc()).limit(1)).first()
        if not r:
            raise HTTPException(404, "todavía no hay informes")
        return {"ts": r.ts, "content": r.content}


@app.get("/signals", dependencies=[Depends(auth)])
def signals(symbol: str | None = None, limit: int = Query(50, le=500), alerted: bool = False, evaluated: bool = False):
    with agent().db.session() as s:
        q = select(Signal).order_by(Signal.ts.desc()).limit(limit)
        if symbol:
            q = q.where(Signal.symbol == symbol.upper())
        if alerted:
            q = q.where(Signal.alerted.is_(True))
        if evaluated:
            q = q.where(Signal.evaluated.is_(True), Signal.kind == "full")
        return [
            {
                "ts": r.ts, "kind": r.kind, "symbol": r.symbol, "price": r.price, "score": r.score,
                "label": r.label, "confidence": r.confidence, "plan": r.plan,
                "ret_24h": r.ret_24h, "ret_72h": r.ret_72h, "outcome": r.outcome,
            }  # fmt: skip
            for r in s.scalars(q)
        ]


@app.get("/performance", dependencies=[Depends(auth)])
def performance(days: int = 30):
    return performance_summary(agent().db, days)


# --------------------------------------------------------------- dashboard
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    """Página estática: pide el API_TOKEN en el navegador y consulta la API con él."""
    return FileResponse(DASHBOARD, headers={"Cache-Control": "no-store"})


@app.get("/stats/effectiveness", dependencies=[Depends(auth)])
def stats_effectiveness(days: int = Query(90, ge=1, le=730)):
    a = agent()
    sc = a.cfg.scoring
    return effectiveness(a.db, days, sc.signal_threshold, sc.strong_threshold)


# ----------------------------------------------------------------- trading
class ModeRequest(BaseModel):
    mode: str
    close_all: bool = False


@app.get("/trading/status", dependencies=[Depends(auth)])
async def trading_status():
    tr = agent().trader
    symbols = sorted({t.symbol for m in ("paper", "live") for t in tr._trades(m, "open")})
    try:
        prices = await tr.prices(symbols) if symbols else {}
    except Exception:
        prices = {}
    return tr.status(prices)


@app.get("/trading/trades", dependencies=[Depends(auth)])
def trading_trades(limit: int = Query(100, le=1000)):
    return agent().trader.trades(limit)


@app.post("/trading/mode", dependencies=[Depends(auth)])
async def trading_mode(req: ModeRequest):
    ok, msg = await agent().trader.set_mode(req.mode, "dashboard", req.close_all)
    if not ok:
        raise HTTPException(409, msg)
    return {"ok": True, "message": msg}
