"""Persistencia (SQLAlchemy 2.0). SQLite por defecto; Postgres cambiando DATABASE_URL."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, delete, event, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(8), default="full")  # full | fast
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Resultado medido a posteriori (evaluation.py)
    evaluated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ret_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_72h: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)  # target | stop | open


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="daily")
    content: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON)


class ComponentStat(Base):
    __tablename__ = "component_stats"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    ic: Mapped[float] = mapped_column(Float)  # correlación de Spearman score→retorno 72h
    hit_rate: Mapped[float] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer)
    weight_mult: Mapped[float] = mapped_column(Float, default=1.0)
    updated: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Trade(Base):
    """Operación del módulo de trading (simulada o real). Sólo largos en spot."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(8), index=True)  # paper | live
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(8), default="open", index=True)  # open | closed
    entry_ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    entry_price: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)
    risk_usd: Mapped[float] = mapped_column(Float)
    fees_usd: Mapped[float] = mapped_column(Float, default=0.0)
    signal_score: Mapped[float] = mapped_column(Float)
    signal_confidence: Mapped[float] = mapped_column(Float)
    exit_ts: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KV(Base):
    """Estado de ejecución persistente (modo de trading elegido en el dashboard, motivo de pausa…)."""

    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, url: str):
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.url = url
        self.engine = create_engine(url, pool_pre_ping=True)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _pragmas(conn, _):  # WAL: lecturas de la API sin bloquear al escáner
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self.Session()

    def last_signal(self, symbol: str, kind: str = "full") -> Signal | None:
        with self.session() as s:
            q = select(Signal).where(Signal.symbol == symbol, Signal.kind == kind).order_by(Signal.ts.desc()).limit(1)
            return s.scalars(q).first()

    def last_alert(self, symbol: str) -> Signal | None:
        with self.session() as s:
            q = select(Signal).where(Signal.symbol == symbol, Signal.alerted.is_(True)).order_by(Signal.ts.desc())
            return s.scalars(q.limit(1)).first()

    def get_kv(self, key: str, default=None):
        with self.session() as s:
            row = s.get(KV, key)
            return row.value.get("v") if row else default

    def set_kv(self, key: str, value) -> None:
        with self.session() as s:
            row = s.get(KV, key) or KV(key=key, value={})
            row.value, row.updated = {"v": value}, utcnow()
            s.add(row)
            s.commit()

    def adaptive_weights(self) -> dict[str, float]:
        with self.session() as s:
            return {c.name: c.weight_mult for c in s.scalars(select(ComponentStat))}

    def prune(self, days: int = 30) -> None:
        """Retención: borra señales rápidas viejas y el detalle JSON de las completas (se conservan scores y resultados)."""
        cutoff = utcnow() - dt.timedelta(days=days)
        with self.session() as s:
            s.execute(delete(Signal).where(Signal.kind == "fast", Signal.ts < cutoff))
            s.execute(update(Signal).where(Signal.ts < cutoff, Signal.details.is_not(None)).values(details=None))
            s.commit()

    def backup(self, dest_dir: str) -> str | None:
        """Copia consistente de SQLite (VACUUM INTO). Para Postgres usar pg_dump."""
        if not self.url.startswith("sqlite"):
            return None
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(dest_dir) / f"cryptoagent-{utcnow():%Y%m%d}.db"
        dest.unlink(missing_ok=True)
        with self.engine.connect() as conn:
            conn.exec_driver_sql(f"VACUUM INTO '{dest}'")
        # conservar 7 copias
        for old in sorted(Path(dest_dir).glob("cryptoagent-*.db"))[:-7]:
            old.unlink()
        return str(dest)
