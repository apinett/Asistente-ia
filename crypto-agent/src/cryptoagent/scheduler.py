"""Planificación de tareas continuas con APScheduler (AsyncIOScheduler)."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .agent.orchestrator import CryptoAgent

log = logging.getLogger(__name__)


def _guard(name: str, fn):
    async def run():
        try:
            await fn()
        except Exception:  # un job fallido nunca debe matar al agente
            log.exception("job %s falló", name)

    run.__name__ = name
    return run


def build_scheduler(agent: CryptoAgent, tz: str, backup_dir: str) -> AsyncIOScheduler:
    sc = agent.cfg.schedule
    sched = AsyncIOScheduler(timezone=tz, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})

    async def backup():
        await asyncio.to_thread(agent.db.prune, 30)
        path = await asyncio.to_thread(agent.db.backup, backup_dir)
        log.info("backup: %s", path)

    sched.add_job(
        _guard("full_scan", lambda: agent.scan("full")),
        IntervalTrigger(minutes=sc.full_scan_minutes),
        id="full_scan",
        next_run_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=10),  # primer escaneo al arrancar
    )
    sched.add_job(_guard("fast_scan", lambda: agent.scan("fast")), IntervalTrigger(minutes=sc.fast_scan_minutes), id="fast_scan")
    sched.add_job(_guard("evaluate", agent.evaluate), IntervalTrigger(minutes=sc.evaluate_minutes), id="evaluate")
    sched.add_job(_guard("daily_report", agent.daily_report), CronTrigger(hour=sc.daily_report_hour, minute=2), id="daily_report")
    sched.add_job(_guard("backup", backup), CronTrigger(hour=sc.backup_hour, minute=17), id="backup")
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    return sched
