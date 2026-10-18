# LPF — Leverage & Positioning Flow

**Análisis de flujo de posicionamiento y apalancamiento.** Es el tipo de análisis "nuevo" del agente,
pensado para cómo se forma hoy el precio en cripto.

## Por qué hace falta

El análisis técnico clásico se diseñó para mercados *spot* donde precio y volumen bastaban para leer
la oferta y la demanda. El mercado cripto actual funciona de otra manera:

1. **Los perpetuos dominan la formación de precio.** El volumen de derivados supera varias veces al spot.
   Muchas subas y caídas violentas no responden a compradores o vendedores nuevos, sino a
   **posiciones apalancadas forzadas a cerrar** (liquidaciones en cascada).
2. **El apalancamiento deja huellas públicas y gratuitas**: open interest, funding, premium del perpetuo
   contra el índice, ratios long/short y flujo agresor (taker) por vela.
3. **No todas las subas valen lo mismo.** Una suba comprada en spot con dinero nuevo suele sostenerse.
   Una suba empujada por perpetuos con funding caro o por cierre de cortos suele revertir.

LPF lee esas huellas para responder tres preguntas que el gráfico no responde:
**¿quién empuja el precio?, ¿con cuánto apalancamiento? y ¿dónde está el combustible de la próxima cascada?**

## Los seis bloques

Todos usan endpoints públicos de Binance Futures (sin API key), con resolución de 1h y ventana de 24 velas.

### 1. Cuadrante precio / open interest (25%)

| Precio | OI | Lectura | Aporte |
|---|---|---|---|
| ↑ | ↑ | **Nuevos largos**: entra dinero a favor de la suba | +0.6 |
| ↑ | ↓ | **Cierre de cortos**: suba por recompra forzada, suele agotarse | +0.15 |
| ↓ | ↑ | **Nuevos cortos**: entra dinero apostando a la baja | −0.6 |
| ↓ | ↓ | **Liquidación de largos**: limpieza de apalancamiento | −0.15 |
| ↓↓ | ↓↓ (−5%) + funding negativo | **Capitulación**: suele marcar suelos locales | +0.3 |

La intensidad escala con el cambio de OI: un 3% en 24h equivale a la señal completa.

### 2. Hacinamiento o crowding (20%, contrarian)

- **Z-score del funding** contra sus últimos 30 días. Un funding extremo indica que un lado paga caro
  por estar posicionado y que es frágil.
- Funding anualizado > 40% penaliza (largos hacinados); < −15% favorece (combustible para short squeeze).
- **Premium mark/índice** > 0.1% = demanda apalancada excesiva.

### 3. Liderazgo del flujo: CVD spot vs perpetuo (25%)

Delta agresor = (compras taker − ventas taker) / volumen, medido por separado en spot y en perpetuo.

| Situación | Lectura |
|---|---|
| Sube el precio y el delta spot es positivo y mayor que el del perpetuo | **Suba sana**, liderada por spot |
| Sube el precio, el delta spot es ≤ 0 y el del perpetuo es > 0 | **Suba frágil**: sólo la sostiene el apalancamiento |
| Baja el precio y el delta spot es positivo | **Absorción**: el spot compra la caída |
| Baja el precio y el delta spot es negativo | **Distribución** en spot |

### 4. Smart money vs retail (15%)

Compara el ratio long/short **de posiciones de los top traders** con el **de cuentas globales** (retail).
Que los top traders estén más largos que el retail es favorable. Lo contrario indica cautela:
históricamente el retail suele estar del lado equivocado en los extremos.

### 5. Riesgo de squeeze (10%)

- **Short squeeze**: funding z < −1, OI subiendo más de 2% y el precio que no cae. Los cortos se acumulan
  sin lograr bajar el precio, que es el combustible típico de una suba violenta.
- **Long squeeze**: el caso simétrico (funding z > 1, OI subiendo y el precio que no avanza).

### 6. Mapa estimado de liquidaciones (5%)

Cada aumento de OI en una vela se interpreta como posiciones nuevas abiertas al cierre. Se reparten
entre largos y cortos según el flujo taker de esa vela, y entre niveles de apalancamiento típicos
(10x 35%, 25x 35%, 50x 20%, 100x 10%). Para cada nivel se calcula el precio de liquidación
(`entrada × (1 ∓ 1/apalancamiento)`). **Los niveles que el precio ya atravesó se descartan**, porque
esas posiciones ya se liquidaron. Queda un mapa de clusters encima (cortos) y debajo (largos) del precio.
El precio tiende a buscar las zonas con más liquidez, por eso el desbalance dentro de ±5% suma un sesgo leve.

> Es una **estimación** (el libro real de liquidaciones no es público). Sirve para ubicar zonas
> probables de aceleración y para no poner stops justo en un cluster.

## Momentum ajustado por apalancamiento

Además del score LPF (−1 a +1, con peso 17% en el score final), LPF produce un multiplicador
**`momentum_quality` (0.6x–1.3x)** que se aplica a los componentes de **tendencia y momentum**:

| Situación | Efecto |
|---|---|
| Entra OI nuevo a favor del movimiento | +0.15 |
| Movimiento liderado por spot | +0.15 |
| Movimiento por cierre forzado (short covering o liquidaciones) | −0.15 |
| Suba liderada sólo por perpetuos | −0.20 |
| Riesgo de squeeze en contra | −0.15 |

Así, un RSI 68 con MACD alcista **no vale lo mismo** si lo sostiene compra spot con OI nuevo
(momentum de calidad, ×1.3) que si lo sostiene funding caro y cierre de cortos (momentum frágil, ×0.6).
La mayoría de los indicadores técnicos no hace esta distinción.

## Cómo se valida que funciona

Ningún análisis debe darse por efectivo sin evidencia. El agente lo mide solo:

1. Cada escaneo guarda los scores de **todos los componentes**, LPF incluido.
2. A las 72h, `evaluation.py` compara cada señal con el retorno real y calcula el **IC**
   (correlación de Spearman entre score y retorno) de cada componente.
3. Con 50 o más señales evaluadas, el peso de cada componente se ajusta dentro de un rango acotado
   (`1 + 3·IC`, entre 0.5x y 1.5x). Si LPF no aporta en tu universo de activos, su peso baja solo.
4. `GET /performance` muestra el IC, el hit rate y el multiplicador de cada componente.

**Recomendación:** dejá correr el agente 3 a 4 semanas antes de operar con sus señales y revisá `/performance`.
Un IC sostenido de 0.03–0.05 ya se considera útil en finanzas cuantitativas. Si un componente tiene IC negativo
de forma persistente, bajá su peso base en `config/settings.yaml`.

## Limitaciones

- Binance guarda sólo **30 días** de OI y ratios long/short, por eso LPF no puede backtestearse años
  hacia atrás. Su validación es *forward* (en vivo).
- Usa datos de un solo exchange. Binance es el de mayor OI, pero no es todo el mercado.
- El mapa de liquidaciones es un modelo y no reemplaza datos propietarios (Coinglass, Hyblock).
