# Investigación de repositorios de GitHub

Antes de escribir código se evaluaron repositorios de GitHub por estrellas, mantenimiento reciente
(último push), licencia y reputación. Datos consultados el 18/10/2026.

## Seleccionados

| Repositorio | ⭐ | Último push | Licencia | Uso en el agente | ¿Completo o parcial? |
|---|---|---|---|---|---|
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | 44.4k | 17/10/2026 | MIT | Datos de spot y perpetuos: velas, tickers, funding, open interest y endpoints crudos de Binance | **Librería completa**: es el estándar de facto, evita escribir un cliente por exchange y trae rate limiting y reintentos. Usamos `ccxt.async_support` para pedir en paralelo. |
| [TA-Lib/ta-lib-python](https://github.com/TA-Lib/ta-lib-python) | 12.3k | 18/10/2026 | BSD | Indicadores (EMA, RSI, MACD, ADX, ATR, Bollinger, OBV, MFI, StochRSI) y **61 detectores de patrones de velas** | **Librería completa**: está en C, es rápida y está probada desde hace 20 años. Desde la 0.6 trae wheels con la librería C incluida (antes había que compilarla). |
| [hmmlearn/hmmlearn](https://github.com/hmmlearn/hmmlearn) | 3.4k | 18/10/2026 | BSD | Régimen de mercado (HMM de 3 estados sobre BTC diario) | **Sólo `GaussianHMM`**. Es opcional: si falla, el agente usa el régimen por reglas. |
| [agronholm/apscheduler](https://github.com/agronholm/apscheduler) | 7.6k | 17/10/2026 | MIT | Ejecución continua: escaneos cada 15/60 min, informe diario, evaluación, backups | **Rama 3.x completa**. La 4.x es una reescritura que cambia la API, por eso se fija `<4`. |
| [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) | 2.1k | 03/04/2026 | MIT | Referencia para la estructura de mercado (BOS/CHoCH, FVG, liquidez) | **Sólo la lógica, reimplementada** (`analysis/structure.py`, unas 150 líneas). Instalar el paquete suma numba y fija versiones de pandas, y su detección de swings mira velas futuras, algo que en vivo genera señales que después desaparecen. |

## Usados como referencia, no como dependencia

| Repositorio | ⭐ | Por qué no se integra |
|---|---|---|
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 55.5k | Es un bot de *ejecución* completo (órdenes, wallets, hyperopt), demasiado para un agente de *análisis*, y su licencia es GPL-3.0: copiarle código obliga a liberar el proyecto bajo GPL. Se tomaron ideas como el filtrado del universo por volumen y el descarte de la vela abierta. Si más adelante querés ejecutar órdenes, lo recomendable es correr freqtrade **al lado** del agente y alimentarlo con las señales de la API. |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 20.5k | Apunta a market making y HFT, que es otro problema. |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | 8.7k | Es un framework de backtesting y trading con su propio runtime, cuando acá alcanza con un backtest walk-forward de componentes. |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | 29.5k | Es excelente para bots conversacionales, pero acá sólo se necesita `sendMessage`. Alcanza con una llamada HTTP de 20 líneas con `httpx`. |

## Descartados

| Repositorio | Motivo |
|---|---|
| twopirllc/pandas-ta | El repositorio original ya no existe en GitHub: no hay mantenimiento confiable. |
| [bukosabino/ta](https://github.com/bukosabino/ta) (5.2k ⭐) | Tiene 159 issues abiertos y es más lento que TA-Lib (pandas puro). Además no trae patrones de velas. |
| [CryptoSignal/Crypto-Signal](https://github.com/CryptoSignal/Crypto-Signal) (5.6k ⭐) | Sin push desde 07/2024 y con dependencias viejas. |
| [ccxt/binance-trade-bot](https://github.com/ccxt/binance-trade-bot) | Es una estrategia de rotación puntual, no un motor de análisis. |

## Resultado

Las piezas de bajo nivel (conectividad con exchanges, indicadores, patrones, HMM, scheduler) usan
librerías maduras. El código propio se concentra en lo que no existe empaquetado:
el **motor de confluencia multi-timeframe**, el **análisis LPF de posicionamiento**, el
**filtro de contexto de velas**, la **auto-evaluación con pesos adaptativos** y la orquestación 24/7.
