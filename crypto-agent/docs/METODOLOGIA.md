# Metodología de análisis

Cada activo se analiza en **4 temporalidades** (1d, 4h, 1h, 15m) y **7 componentes**, y todo se combina en un
**score de −100 a +100** con un nivel de confianza y un plan operativo.

## 1. Componentes por temporalidad

### Tendencia (`scoring.trend_score`, peso base 22%)
- Alineación: precio > EMA20 > EMA50 > EMA200 (cada condición suma ±0.25).
- **Supertrend (10, 3)**: dirección ±0.25.
- **ADX(14)**: escala la intensidad. Con ADX 15 la tendencia vale 50%; con ADX 40 o más, 100%.

### Momentum (`analysis/momentum.py`, 20%)
| Indicador | Uso |
|---|---|
| RSI(14) | En tendencia, RSI > 50 confirma fuerza. En rango, < 30 y > 70 son reversión. |
| MACD(12,26,9) | Signo del histograma (60%) y su aceleración (40%). Se informan los cruces. |
| StochRSI(14,3,3) | Cruces en zonas extremas (< 25 y > 75), para el timing fino. |
| ROC(10) | Normalizado por ATR%: un 5% en BTC pesa más que un 5% en una memecoin. |
| MFI(14) | Momentum ponderado por volumen. |
| **Divergencias** | Regulares (reversión, ±0.35) y ocultas (continuación, ±0.2) entre precio y RSI en los pivots confirmados. Si el histograma MACD muestra la misma divergencia, pesa ×1.3. |

### Volumen (10%)
- Pendiente del **OBV** en 20 velas, normalizada por el volumen medio.
- **CMF(20)** (Chaikin Money Flow): presión compradora o vendedora.
- **Volumen relativo**: una vela con volumen superior a 1x la media confirma su dirección.

### Patrones de velas (`analysis/candles.py`, 8%)
Se usan los **61 detectores de TA-Lib** sobre las últimas 3 velas. Ningún patrón cuenta solo: cada detección se pondera así:

| Factor | Efecto |
|---|---|
| Fiabilidad histórica del patrón (envolvente 0.8, estrella de la mañana 0.85, martillo 0.65, harami 0.5, resto 0.4) | base |
| Tendencia previa adecuada (un patrón alcista tras una caída) | ×1.3; si es inadecuada, ×0.6 |
| En soporte o resistencia (a menos de 1 ATR de un nivel) | ×1.4 |
| Volumen relativo > 1.3 | ×1.2 |
| Confirmado por la vela siguiente / invalidado | ×1.3 / ×0.2 |
| Antigüedad (cada vela hacia atrás) | −20% |

Los dojis y los spinning tops se registran como **indecisión**, sin dirección.

### Estructura (`analysis/structure.py`, 15%)
- **Pivots confirmados** (3 velas a cada lado, sin mirar el futuro).
- **Tendencia estructural**: HH/HL (alcista), LH/LL (bajista) o lateral.
- **BOS / CHoCH**: ruptura de estructura a favor de la tendencia o cambio de carácter.
- **Soportes y resistencias**: clusters de pivots agrupados dentro de 0.5 ATR, con número de toques.
- **Fair Value Gaps** de 3 velas no rellenados.
- Estar a menos de 1 ATR de un soporte con 2 o más toques suma, y lo mismo frente a una resistencia resta.

## 2. Componentes por activo

- **Posicionamiento LPF (17%)**: ver [ANALISIS_LPF.md](ANALISIS_LPF.md).
- **Fuerza relativa vs BTC (8%)**: ROC de 30 días del ratio activo/BTC y si el ratio está sobre su EMA20.
  En cripto los activos que le ganan a BTC tienden a seguir ganándole (momentum transversal).

## 3. Régimen de mercado

**Por activo** (`regime.rule_regime`):

| Régimen | Condición | Ajuste de pesos |
|---|---|---|
| tendencia alcista/bajista | ADX ≥ 23, EMAs alineadas, DI a favor | tendencia ×1.3, momentum ×1.1, patrones ×0.7 |
| lateral | resto | tendencia ×0.6, patrones ×1.3, estructura ×1.3 |
| alta volatilidad | ATR% en el percentil > 95 y ADX < 25 | posicionamiento ×1.4, el resto se atenúa |

**Mercado global**: un HMM gaussiano de 3 estados sobre retorno y volatilidad de BTC diario clasifica el régimen en
*expansión alcista*, *acumulación/lateral* o *contracción bajista*, con su probabilidad. Va al informe diario.

## 4. Combinación

```
s_c       = Σ_tf  peso_tf · score_c,tf            (1d 35%, 4h 35%, 1h 20%, 15m 10%)
s_c       = s_c · momentum_quality                (sólo tendencia y momentum; LPF)
w_c       = peso_base_c · m_régimen(c) · m_adaptativo(c)
score     = 100 · Σ w_c · s_c / Σ w_c
alineación = % del peso temporal cuyo sesgo coincide con el signo del score
confianza = (0.5·alineación + 0.5·min(|score|/70, 1)) · completitud_de_datos
```

| Score | Etiqueta |
|---|---|
| ≥ +55 | ALCISTA FUERTE |
| +25 a +55 | ALCISTA |
| −25 a +25 | NEUTRAL |
| −55 a −25 | BAJISTA |
| ≤ −55 | BAJISTA FUERTE |

## 5. Plan operativo (temporalidad principal 4h)

Para las señales alcistas (las bajistas son simétricas):
- **Stop**: 0.3 ATR por debajo del soporte más cercano, si está a menos de 2.5 ATR. Si no hay soporte cerca, precio − 2 ATR.
- **Zona de entrada**: entre el soporte (o precio − 0.5 ATR) y el precio actual.
- **Objetivos**: las resistencias que estén al menos a 1R. Si no hay, 1.5R y 3R.
- **R:R** respecto del primer objetivo e **invalidación** explícita.

## 6. Estudio continuo y auto-evaluación

| Tarea | Frecuencia | Qué hace |
|---|---|---|
| Escaneo completo | 60 min | Top 40 por volumen, 4 temporalidades + LPF + fuerza relativa + HMM |
| Escaneo rápido | 15 min | Top 15 en 1h/15m. Alerta de *timing* sólo si coincide con el sesgo del escaneo completo |
| Evaluación | 60 min | Retorno a 24h/72h de cada señal, si tocó objetivo o stop, IC por componente y pesos adaptativos |
| Informe diario | 09:02 (TZ) | Macro (Fear & Greed, dominancia, stablecoins), amplitud, régimen, top alcistas/bajistas, LPF de BTC/ETH y desempeño. Narrativa con Claude |
| Monitor de trading | 1 min | Stops, objetivos, cierre por tiempo y kill switch de las posiciones simuladas o reales (ver [TRADING.md](TRADING.md)) |
| Backup y retención | 03:17 | `VACUUM INTO` (7 copias). Purga del detalle de más de 30 días |

## 7. Backtest

`python -m cryptoagent backtest -s BTC/USDT -t 4h -d 730` hace un walk-forward sin look-ahead y reporta
por componente el IC, el hit rate y el retorno medio con score > 0.3 o < −0.3.
LPF no se backtestea porque Binance sólo guarda 30 días de OI; se valida en vivo.
