"""Configuración: YAML para parámetros de análisis + variables de entorno para secretos."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


class ExchangeCfg(BaseModel):
    spot: str = "binance"
    derivatives: str = "binanceusdm"
    quote: str = "USDT"


class UniverseCfg(BaseModel):
    top_n: int = 40
    always_include: list[str] = ["BTC/USDT", "ETH/USDT"]
    exclude_bases: list[str] = []
    min_quote_volume_usd: float = 20_000_000


class PositioningCfg(BaseModel):
    enabled: bool = True
    period: str = "1h"
    lookback_bars: int = 24
    leverage_tiers: dict[int, float] = {10: 0.35, 25: 0.35, 50: 0.20, 100: 0.10}


class ScoringCfg(BaseModel):
    weights: dict[str, float] = {
        "trend": 0.22,
        "momentum": 0.20,
        "volume": 0.10,
        "patterns": 0.08,
        "structure": 0.15,
        "positioning": 0.17,
        "relative_strength": 0.08,
    }
    strong_threshold: float = 55
    signal_threshold: float = 25
    adaptive_weights: bool = True


class AlertsCfg(BaseModel):
    min_abs_score: float = 55
    cooldown_hours: float = 12
    max_per_scan: int = 8


class ScheduleCfg(BaseModel):
    fast_scan_minutes: int = 15
    full_scan_minutes: int = 60
    daily_report_hour: int = 9
    evaluate_minutes: int = 60
    backup_hour: int = 3


class ReadinessCfg(BaseModel):
    """Umbrales del 'nivel de confianza' que habilita el modo real."""

    min_days: int = 21
    min_evaluated: int = 300
    min_qualifying: int = 30
    min_hit_rate: float = 0.55
    min_expectancy_r: float = 0.15
    min_ic: float = 0.03
    min_paper_trades: int = 20
    min_profit_factor: float = 1.2


class TradingCfg(BaseModel):
    mode: str = "paused"  # paused | paper | live
    paper_starting_balance: float = 10_000
    live_capital_usd: float = 500  # capital máximo que el agente puede usar en real
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 10.0
    max_open_positions: int = 5
    min_score: float = 55
    min_confidence: float = 0.6
    min_risk_reward: float = 1.5
    max_hold_hours: float = 168
    daily_loss_limit_pct: float = 3.0
    kill_switch_close_positions: bool = True
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    min_notional_usd: float = 10
    allowed_symbols: list[str] = []
    require_readiness_for_live: bool = True
    readiness: ReadinessCfg = ReadinessCfg()


class AgentConfig(BaseModel):
    exchange: ExchangeCfg = ExchangeCfg()
    universe: UniverseCfg = UniverseCfg()
    timeframes: dict[str, float] = {"1d": 0.35, "4h": 0.35, "1h": 0.20, "15m": 0.10}
    primary_timeframe: str = "4h"
    candles_limit: int = 400
    positioning: PositioningCfg = PositioningCfg()
    scoring: ScoringCfg = ScoringCfg()
    alerts: AlertsCfg = AlertsCfg()
    schedule: ScheduleCfg = ScheduleCfg()
    trading: TradingCfg = TradingCfg()
    concurrency: int = 6


class Secrets(BaseSettings):
    """Valores sensibles y de despliegue: sólo desde el entorno / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    api_token: str = ""
    # Trading real: las tres deben estar presentes para que el modo "live" sea siquiera posible
    binance_api_key: str = ""
    binance_api_secret: str = ""
    trading_live_enabled: bool = False
    database_url: str = "sqlite:///./storage/cryptoagent.db"
    config_path: str = Field(default=str(DEFAULT_CONFIG))
    log_level: str = "INFO"
    tz: str = "UTC"


def load_config(path: str | Path) -> AgentConfig:
    p = Path(path)
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return AgentConfig.model_validate(raw or {})


@lru_cache
def get_secrets() -> Secrets:
    return Secrets()


@lru_cache
def get_config() -> AgentConfig:
    return load_config(get_secrets().config_path)
