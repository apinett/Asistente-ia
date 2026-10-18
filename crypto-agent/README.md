# 🤖 Crypto Agent — agente de análisis continuo del mercado cripto

Agente autónomo que corre 24/7 en tu VPS y analiza todo el mercado cripto:

- **Análisis técnico multi-timeframe** (1d, 4h, 1h, 15m): EMAs, ADX, Supertrend, Bollinger/Keltner (squeeze), ATR.
- **Momentum**: RSI, MACD, StochRSI, ROC normalizado por volatilidad, MFI y **divergencias** regulares y ocultas.
- **Patrones de velas**: 61 detectores de TA-Lib con **filtro de contexto** (tendencia previa, soporte/resistencia, volumen, confirmación).
- **Estructura de mercado**: pivots, soportes/resistencias, BOS/CHoCH y Fair Value Gaps.
- **Estudio de mercado continuo**: universo dinámico (top 40 por volumen), fuerza relativa vs BTC, amplitud, régimen (HMM), macro (Fear & Greed, dominancia, stablecoins).
- **🆕 LPF — Leverage & Positioning Flow**: análisis del posicionamiento en derivados (cuadrante precio/OI, funding z-score, CVD spot vs perpetuo, top traders vs retail, riesgo de squeeze, mapa estimado de liquidaciones) y **momentum ajustado por apalancamiento**. Ver [docs/ANALISIS_LPF.md](docs/ANALISIS_LPF.md).
- **Auto-evaluación**: mide el acierto de sus propias señales a 72h y **recalibra los pesos** de cada componente según el IC observado.
- **Salidas**: alertas e informe diario por **Telegram** (con narrativa de Claude), API HTTP y base de datos con el historial.

> ⚠️ Es una herramienta de análisis, no de asesoramiento financiero. Validá el desempeño con `/performance` antes de operar con sus señales.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/REPOSITORIOS.md](docs/REPOSITORIOS.md) | Investigación de repos de GitHub: qué se usa completo, qué parcial y qué se descartó |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Módulos, flujo de datos, base de datos, API y presupuesto de recursos del VPS |
| [docs/METODOLOGIA.md](docs/METODOLOGIA.md) | Fórmulas y reglas de cada componente, scoring, plan operativo y auto-evaluación |
| [docs/ANALISIS_LPF.md](docs/ANALISIS_LPF.md) | El análisis nuevo: fundamentos, cálculo, validación y limitaciones |

## Ejemplo de alerta (valores ilustrativos)

```
🟢🟢 ETH/USDT — ALCISTA FUERTE
Score +70/100 · confianza 0.86 · precio 3,412
Plan (4h, long): entrada 3,385–3,412 | stop 3,301 | objetivos 3,580 / 3,700 | R:R 1.5
LPF +0.33 · funding 11.0% anual · OI +6.2% · calidad momentum x1.30
Claves:
• [1d] BOS alcista
• [1d] vela envolvente alcista (en soporte, confirmado)
• [LPF] cuadrante precio/OI: nuevos largos
• [LPF] flujo liderado por spot (suba sana)
⚠️ Análisis automatizado con fines informativos. No es asesoramiento financiero.
```

## Prueba local

```bash
cd crypto-agent
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                                   # 26 tests, sin red
PYTHONPATH=src python -m cryptoagent scan -s BTC/USDT ETH/USDT SOL/USDT
PYTHONPATH=src python -m cryptoagent backtest -s BTC/USDT -t 4h -d 730
```

## Despliegue en el VPS Hostinger (KVM 2 · Ubuntu 24.04 con Coolify)

### Antes de empezar
1. **Bot de Telegram**: hablale a [@BotFather](https://t.me/BotFather), `/newbot` → copiá el token. Mandale un mensaje a tu bot
   y obtené tu chat id con [@userinfobot](https://t.me/userinfobot).
2. **API key de Claude** (opcional, para la narrativa del informe): [console.anthropic.com](https://console.anthropic.com).
   Sin ella el agente funciona igual y usa un informe por plantilla.
3. **Token de la API**: `openssl rand -hex 32`.

### Opción A: Coolify (recomendada)
1. Entrá al panel de Coolify (`http://187.127.49.189:8000`, o el dominio que hayas configurado).
2. **Projects → + New → Add Resource → Private Repository (GitHub App)** y elegí `apinett/asistente-ia`, con la rama
   en la que esté este código.
3. **Build Pack: Docker Compose** · **Base Directory: `/crypto-agent`** · **Docker Compose Location: `/docker-compose.yml`**.
4. En **Environment Variables** cargá: `API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`
   (opcional) y `TZ=America/Argentina/Buenos_Aires`.
5. (Opcional) En **Domains** del servicio `crypto-agent`: `https://agente.tudominio.com:8000`. Coolify emite el
   certificado TLS y enruta al puerto interno 8000.
6. **Deploy**. En los logs deberías ver `universo: 40 activos` y `escaneo full: 40 activos en XXs`.
   El volumen `agent-storage` conserva la base y los backups entre despliegues.

### Opción B: Docker Compose directo por SSH
```bash
ssh root@187.127.49.189
git clone https://github.com/apinett/asistente-ia.git && cd asistente-ia/crypto-agent
cp .env.example .env && nano .env          # completar tokens
docker compose up -d --build
docker compose logs -f
```
Para exponer la API sin Coolify, descomentá `ports` en `docker-compose.yml` (puerto 8080 del host, porque
el 8000 lo ocupa Coolify) y poné un proxy con HTTPS delante.

### Uso de la API
```bash
TOKEN=...; URL=https://agente.tudominio.com
curl -H "Authorization: Bearer $TOKEN" $URL/market            # ranking del mercado
curl -H "Authorization: Bearer $TOKEN" $URL/symbol/BTC        # análisis completo de BTC
curl -H "Authorization: Bearer $TOKEN" $URL/performance       # desempeño medido de las señales
curl -X POST -H "Authorization: Bearer $TOKEN" $URL/report    # informe diario ahora
```
Comandos manuales dentro del contenedor: `docker compose exec crypto-agent python -m cryptoagent scan -s BTC/USDT`.

## Configuración

Todo se ajusta en [`config/settings.yaml`](config/settings.yaml): tamaño del universo, temporalidades y sus pesos,
pesos de cada componente, umbrales de señal y de alerta, cooldown y horarios. Los secretos van **sólo** en variables de entorno.

## Recomendaciones operativas

- Activá en Hostinger los **backups automáticos** del VPS, o copiá `/app/storage/backups` fuera del servidor.
  Hoy el plan hace backup semanal.
- Dejá correr el agente **3 o 4 semanas** antes de confiar en sus señales y revisá `/performance`: el IC por
  componente te dice qué funciona en el mercado actual.
- Usá el plan (stop/objetivos) como referencia de riesgo, no como orden automática.
