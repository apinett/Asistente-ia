# Arquitectura

## Vista general

```
                    ┌──────────────────────── contenedor crypto-agent (Coolify) ────────────────────────┐
                    │                                                                                    │
 Binance spot  ───► │  market/exchange.py ──► analysis/ (indicadores, momentum, velas, estructura,       │
 Binance futures ─► │  market/derivatives.py        régimen, fuerza relativa, LPF) ──► scoring.py        │
 alternative.me ──► │  market/macro.py                                               │                   │
 CoinGecko     ───► │                                                                ▼                   │
                    │  scheduler.py (APScheduler) ──► agent/orchestrator.py ──► storage/db.py (SQLite)   │
                    │                                   │        │                     ▲                 │
                    │                                   │        └── agent/evaluation.py (IC, pesos)     │
                    │                                   ├──► agent/llm.py ──► Claude API (informe diario) │
                    │                                   └──► notify/telegram.py ──► tu Telegram          │
                    │  api/server.py (FastAPI :8000) ◄── consultas HTTP con Bearer token                 │
                    └────────────────────────────────────────────────────────────────────────────────────┘
```

Un solo proceso: **uvicorn** sirve la API y en su `lifespan` arranca el **AsyncIOScheduler**.
Todo el I/O es asíncrono (ccxt async + httpx). El cálculo con TA-Lib corre en un thread
(`asyncio.to_thread`) para no bloquear la API.

## Estructura de archivos

```
crypto-agent/
├── Dockerfile · docker-compose.yml · .env.example
├── requirements.txt · pyproject.toml
├── config/settings.yaml          # universo, temporalidades, pesos, umbrales, horarios
├── docs/                         # esta documentación
├── src/cryptoagent/
│   ├── __main__.py               # CLI: serve | scan | report | evaluate | backtest
│   ├── config.py                 # YAML + variables de entorno (pydantic-settings)
│   ├── scheduler.py              # tareas periódicas
│   ├── market/
│   │   ├── exchange.py           # ccxt async, reintentos, velas cerradas con volumen taker
│   │   ├── derivatives.py        # OI, funding, premium, ratios L/S
│   │   └── macro.py              # Fear & Greed, dominancia, stablecoins
│   ├── analysis/
│   │   ├── indicators.py         # TA-Lib + Supertrend, squeeze, CMF
│   │   ├── momentum.py           # RSI/MACD/StochRSI/ROC/MFI + divergencias
│   │   ├── candles.py            # 61 patrones + filtro de contexto
│   │   ├── structure.py          # pivots, S/R, BOS/CHoCH, FVG
│   │   ├── regime.py             # reglas + HMM
│   │   ├── relative.py           # fuerza relativa vs BTC, amplitud
│   │   ├── positioning.py        # LPF (análisis nuevo)
│   │   └── scoring.py            # confluencia multi-timeframe y plan
│   ├── agent/
│   │   ├── orchestrator.py       # escaneos, persistencia, alertas, informe
│   │   ├── evaluation.py         # resultados, IC, pesos adaptativos
│   │   ├── backtest.py           # walk-forward
│   │   ├── llm.py                # narrativa con Claude
│   │   ├── report.py             # contexto + informe por plantilla
│   │   └── serialize.py          # dict/JSON y texto de alertas
│   ├── storage/db.py             # SQLAlchemy: signals, reports, component_stats
│   ├── notify/telegram.py
│   └── api/server.py             # FastAPI
└── tests/                        # 26 tests con datos sintéticos (sin red)
```

## Base de datos

| Tabla | Contenido |
|---|---|
| `signals` | Cada análisis (completo o rápido): score, etiqueta, confianza, componentes, plan, detalle JSON y, a posteriori, `ret_24h`, `ret_72h` y `outcome` (target/stop/abierta) |
| `reports` | Informes diarios con su contexto JSON |
| `component_stats` | IC, hit rate, n y multiplicador de peso de cada componente |

SQLite en modo WAL alcanza para este volumen (unas 2.500 filas por día). Para usar Postgres basta con
cambiar `DATABASE_URL` (por ejemplo, un Postgres creado desde Coolify).

## API

Todas las rutas, excepto `/health`, exigen `Authorization: Bearer $API_TOKEN`.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado, último escaneo y próximos jobs |
| GET | `/market` | Ranking del último escaneo, régimen y amplitud |
| GET | `/symbol/{BASE}` | Análisis completo de un activo (ej. `/symbol/BTC`) |
| GET | `/signals?symbol=&limit=&alerted=` | Historial de señales con resultados |
| GET | `/performance?days=30` | Hit rate, target/stop e IC por componente |
| GET | `/report/latest` | Último informe diario |
| POST | `/scan` | Fuerza un escaneo completo (body opcional: lista de símbolos) |
| POST | `/report` | Genera y envía el informe ahora |

## Presupuesto de recursos (Hostinger KVM 2: 2 vCPU, 8 GB RAM, 100 GB)

| Recurso | Uso estimado | Límite configurado |
|---|---|---|
| CPU | Picos de 20–60 s por escaneo completo, idle el resto | 1.5 vCPU (queda margen para Coolify y Traefik) |
| RAM | 400–700 MB | 2 GB |
| Disco | ~5–10 MB/día antes de la purga de 30 días; backups de 7 días | Muy por debajo de 100 GB |
| Requests a Binance | ~440 por escaneo completo; ~135 por rápido | Weight limit de Binance: 2.400–6.000 por minuto; endpoints `/futures/data`: 1.000 cada 5 min |
| Claude | 1 llamada por día (~10–20k tokens de entrada) | Centavos de dólar por día |

El VPS está en **Brasil (Campinas)**: Binance y Bybit responden desde allí sin restricciones geográficas
(Binance bloquea IPs de EE.UU., no de Brasil).

## Extensiones sugeridas

- **Más exchanges en LPF**: agregar Bybit/OKX con ccxt (`fetch_open_interest_history` es unificado) y sumar el OI.
- **Bot conversacional en Telegram**: comandos `/btc` o `/top`, que consulten la API.
- **Dashboard**: Grafana sobre SQLite/Postgres, o un frontend simple que consuma `/market`.
- **Ejecución**: conectar las señales a freqtrade vía su API REST, con paper trading primero.
