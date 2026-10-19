# Módulo de compra y venta (en pausa por defecto)

El agente puede ejecutar sus propias señales, pero **arranca pausado** y el dinero real queda bloqueado
por varias compuertas independientes. La idea es avanzar en tres etapas, siempre con datos:

```
  ⏸ PAUSADO  ──────►  🧪 SIMULADO (paper)  ──────►  💰 REAL (live)
  sólo analiza        opera con saldo virtual,      órdenes reales en Binance spot,
  y mide su           mismo circuito que el real    con capital limitado y kill switch
  efectividad         (para medir la operatoria)    (sólo con el nivel de confianza al 100%)
```

## Los tres modos

| Modo | Qué hace | Cómo se activa |
|---|---|---|
| **Pausado** (por defecto) | No abre posiciones. Si quedaron abiertas, sigue gestionando sus stops y objetivos para no dejarlas desprotegidas. | Botón *Pausado* del dashboard (opcionalmente cierra todo). |
| **Simulado** | Ejecuta las señales con saldo virtual (10.000 USDT), con comisión (0.1%) y slippage (0.05%). No toca el exchange. | Botón *Simulado* del dashboard. |
| **Real** | Compra y vende en Binance spot con tu cuenta. | Botón *Real*, que sólo se habilita cuando se cumplen **todas** las compuertas. |

El modo elegido queda guardado en la base de datos y sobrevive a reinicios y redeploys.

## Reglas de operación

Sólo **largos en spot**: sin apalancamiento, sin cortos y sin posibilidad de perder más de lo invertido.

| Regla | Valor por defecto (`config/settings.yaml → trading`) |
|---|---|
| Señal mínima para entrar | score ≥ 55 (ALCISTA FUERTE), confianza ≥ 0.60, R:R ≥ 1.5 |
| Riesgo por operación | 1% del capital (lo que se pierde si salta el stop) |
| Tamaño máximo por posición | 10% del capital |
| Posiciones simultáneas | 5 como máximo, una por activo |
| Salidas | stop · objetivo 1 · señal contraria (score ≤ −25) · 7 días máximo |
| **Kill switch** | si la pérdida del día llega al 3% del capital: pausa automática, cierre de posiciones y aviso por Telegram |
| Capital en modo real | `live_capital_usd: 500`. Es el tope que el agente puede usar aunque tengas más en la cuenta. |

Las entradas se deciden tras cada escaneo completo (cada hora). Stops, objetivos y kill switch se
controlan **cada minuto**. Los stops son del agente, no órdenes en el exchange: ante un movimiento muy
brusco entre dos controles, la salida puede ejecutarse peor que el stop. Para eso están el tope de tamaño
y el kill switch.

## Nivel de confianza (readiness)

Es el porcentaje que ves en el dashboard. Mide, **sólo con las señales que el agente habría operado**,
si demostró ventaja estadística:

| Control | Mínimo | Por qué |
|---|---|---|
| Días de historial | 21 | Ver al menos un par de cambios de régimen |
| Señales evaluadas | 300 | Muestra suficiente para que el % no sea suerte |
| Señales operables evaluadas | 30 | Las que cumplen las reglas de entrada |
| Acierto de señales operables | 55% | Mejor que el azar (50%) con margen |
| Expectativa por operación | +0.15 R | Ganancia media positiva medida en múltiplos del riesgo |
| IC del score total | 0.03 | El score ordena bien los resultados |
| Operaciones simuladas cerradas | 20 | La operatoria real (comisiones, salidas) también funciona |
| Profit factor simulado | 1.2 | Ganancias / pérdidas del modo simulado |

Los umbrales se ajustan en `trading.readiness`. **Bajarlos para llegar antes al 100% sólo te engaña a vos.**

## Cómo activar el modo real (cuando llegue el momento)

Hacen falta **cuatro cosas a la vez**: si falta cualquiera, el botón *Real* queda deshabilitado y el
servidor rechaza el cambio aunque se llame a la API directamente.

1. **Nivel de confianza al 100%** en el dashboard.
2. **API key de Binance** con permisos mínimos. En Binance → *Perfil → Gestión de API → Crear API → generada por el sistema*:
   - ✅ *Enable Reading*
   - ✅ *Enable Spot & Margin Trading*
   - ❌ **Withdrawals: desactivado** (el agente nunca necesita retirar fondos)
   - ❌ Futures, Margin y Universal Transfer: desactivados
   - 🔒 **Restrict access to trusted IPs only**: `187.127.49.189`
3. **Variables en Coolify** → *Environment Variables*:
   ```env
   BINANCE_API_KEY=...
   BINANCE_API_SECRET=...
   TRADING_LIVE_ENABLED=true
   ```
   Luego *Redeploy* y verificá con `python -m cryptoagent doctor` (debe mostrar tu saldo USDT libre).
4. En el dashboard, botón **💰 Real**: pide confirmación y que escribas `OPERAR REAL`.

**Recomendación:** empezá con `live_capital_usd` bajo (por ejemplo, 100–200 USDT) durante unas semanas y
compará el resultado real con el simulado antes de subirlo.

### Volver atrás

- **Pausar**: botón *Pausado* (con o sin cerrar posiciones). Es inmediato.
- **Apagar el dinero real de raíz**: `TRADING_LIVE_ENABLED=false` y *Redeploy*. Aunque el modo guardado sea "real",
  el agente queda pausado mientras falte una compuerta.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/trading/status` | Modo pedido y efectivo, compuertas, nivel de confianza, cuentas, posiciones y curva de capital |
| GET | `/trading/trades?limit=100` | Historial de operaciones |
| POST | `/trading/mode` | `{"mode": "paused" \| "paper" \| "live", "close_all": false}`. Devuelve 409 si faltan compuertas. |

## Repositorios evaluados para la ejecución

- **ccxt** (44k ⭐): se usa para las órdenes (`create_order`), los saldos y la precisión de cantidades. Es la misma
  librería que ya usa el análisis, así que no suma dependencias.
- **freqtrade** (55k ⭐): referencia de diseño, no se integra. De ahí salen el concepto de *dry-run* (nuestro
  modo simulado), los límites `max_open_trades`/stoploss y la protección por pérdida diaria. Integrarlo implicaría
  correr un segundo bot con su propia base de datos y estrategia, y adoptar su licencia GPL-3.
