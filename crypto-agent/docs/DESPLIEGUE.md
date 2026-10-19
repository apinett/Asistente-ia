# Despliegue paso a paso en tu VPS (Hostinger KVM 2 · Ubuntu 24.04 con Coolify)

Tiempo estimado: **30–45 minutos**. Datos de tu servidor:

| | |
|---|---|
| IP | `187.127.49.189` |
| Panel de Coolify | `http://187.127.49.189:8000` |
| Repositorio | `https://github.com/apinett/Asistente-ia` (público) |
| Carpeta del agente | `/crypto-agent` |

---

## Paso 0 · Juntá lo que vas a necesitar

1. **Token de la API del agente** (obligatorio). Protege el dashboard y la API. Generalo en cualquier terminal:
   ```bash
   openssl rand -hex 32
   ```
   Guardalo en tu gestor de contraseñas: lo vas a pegar en Coolify y en el dashboard.
2. **Bot de Telegram** (recomendado, para recibir alertas e informes):
   - En Telegram abrí [@BotFather](https://t.me/BotFather), enviá `/newbot`, elegí un nombre y copiá el **token** (`123456:ABC…`).
   - Abrí tu bot nuevo y mandale cualquier mensaje (sin esto el bot no puede escribirte).
   - Abrí [@userinfobot](https://t.me/userinfobot) y copiá tu **Id** numérico: ese es el `TELEGRAM_CHAT_ID`.
3. **API key de Claude** (opcional): [console.anthropic.com](https://console.anthropic.com) → *API Keys*. Sin ella el informe diario
   sale con plantilla en lugar de redactado.
4. **Dominio** (opcional pero recomendado, para tener HTTPS). Si tenés uno en Hostinger, creá un subdominio en el paso 3.

> No hacen falta API keys de Binance para analizar: el agente usa datos públicos. Las keys sólo se necesitan
> el día que actives el trading real (ver [TRADING.md](TRADING.md)).

## Paso 1 · Dejá el código en la rama que vas a desplegar

El agente está en la rama `claude/crypto-agent`. Tenés dos opciones:

- **Recomendada**: en GitHub abrí un *Pull Request* de `claude/crypto-agent` hacia `main` y mergealo. Así desplegás siempre `main`.
- **Rápida**: desplegá directamente la rama `claude/crypto-agent` (en el paso 4 escribís ese nombre de rama).

## Paso 2 · Revisá el firewall de Hostinger

En **hPanel → VPS → Seguridad → Firewall**:

- Si no hay reglas configuradas, todo está abierto y podés seguir.
- Si creaste reglas, asegurate de permitir **TCP 22** (SSH), **80** y **443** (web y HTTPS) y **8000** (panel de Coolify).
  Para mayor seguridad, el 8000 limitalo a tu IP.

El agente **no** necesita puertos propios abiertos: Coolify lo publica por el 80/443.

## Paso 3 · (Opcional) Apuntá un subdominio al VPS

En **hPanel → Dominios → tu dominio → DNS / Nameservers → Administrar registros DNS**, agregá:

| Tipo | Nombre | Apunta a | TTL |
|---|---|---|---|
| A | `agente` | `187.127.49.189` | 3600 |

Quedará `agente.tudominio.com`. La propagación suele tardar entre 5 y 30 minutos.

**Sin dominio:** en el paso 6 Coolify te genera una URL automática del tipo `http://xxxx.187.127.49.189.sslip.io`.
Funciona, pero sin HTTPS el token viaja sin cifrar: usala sólo para probar.

## Paso 4 · Creá el recurso en Coolify

1. Entrá a `http://187.127.49.189:8000`. Si es la primera vez, Coolify te pide crear el usuario administrador.
2. **Projects → + Add**. Nombre: `crypto-agent` → *Continue*. Entrá al entorno `production`.
3. **+ New** → **Public Repository**.
4. Repository URL: `https://github.com/apinett/Asistente-ia` → *Check repository*.
5. Completá:
   - **Branch**: `main` (o `claude/crypto-agent` si elegiste la opción rápida del paso 1).
   - **Build Pack**: `Docker Compose`.
   - **Base Directory**: `/crypto-agent`.
   - **Docker Compose Location**: `/docker-compose.yml`.
6. *Continue*. Coolify lee el `docker-compose.yml` y muestra el servicio `crypto-agent`.

## Paso 5 · Cargá las variables de entorno

En el recurso → pestaña **Environment Variables** → *Developer view*, pegá lo siguiente con tus valores reales:

```env
API_TOKEN=pegá-acá-el-token-del-paso-0
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-opus-5-5
TZ=America/Argentina/Buenos_Aires
TRADING_LIVE_ENABLED=false
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

*Save*. `TRADING_LIVE_ENABLED=false` garantiza que el modo real sea imposible aunque alguien toque el dashboard.

## Paso 6 · Asigná el dominio al servicio

En **Configuration → General**, buscá el servicio `crypto-agent` → campo **Domains**:

- Con dominio propio: `https://agente.tudominio.com:8000`. El `:8000` le indica a Coolify el puerto **interno** del
  contenedor; el público sigue siendo 443. Coolify pide el certificado HTTPS automáticamente.
- Sin dominio: tocá **Generate Domain**.

*Save*.

## Paso 7 · Deploy

Tocá **Deploy** (arriba a la derecha) y seguí los **Logs**:

1. La primera construcción tarda 2–4 minutos (descarga Python y las librerías; TA-Lib viene precompilado).
2. Cuando arranca deberías ver:
   ```
   Application startup complete.
   universo: 40 activos
   escaneo full: 40 activos en 35.2s
   ```
3. El estado del recurso pasa a **Running (healthy)**: el healthcheck consulta `/health` cada minuto.

## Paso 8 · Verificá la instalación con `doctor`

En Coolify → recurso → **Terminal** → elegí el contenedor `crypto-agent` y ejecutá:

```bash
python -m cryptoagent doctor
```

Salida esperada:

```
Crypto Agent · diagnóstico

  ✔ Configuración: /app/config/settings.yaml · universo top 40 · trading 'paused'
  ✔ Base de datos: sqlite:////app/storage/cryptoagent.db
  ✔ Exchange spot (binance): BTC/USDT 67,250.00
  ✔ Derivados LPF (binanceusdm): OI ok · funding ok · L/S ok · CVD ok
  ✔ Datos macro: fear_greed, global, stablecoins
  ✔ Telegram: mensaje de prueba enviado
  – Claude: sin ANTHROPIC_API_KEY: el informe usa plantilla
  ✔ API_TOKEN: configurado
  – API key de Binance (trading): no cargada: sólo modos pausado y simulado

Resultado: OK
```

Además te tiene que llegar a Telegram el mensaje "✅ Crypto Agent: prueba de conexión desde el VPS".

Otros comandos útiles desde la misma terminal:

```bash
python -m cryptoagent scan -s BTC/USDT ETH/USDT        # análisis inmediato de un par de activos
python -m cryptoagent report                           # manda el informe diario ahora
python -m cryptoagent backtest -s BTC/USDT -t 4h -d 730
```

## Paso 9 · Abrí el dashboard

Entrá a `https://agente.tudominio.com/dashboard` (o la URL generada), pegá tu `API_TOKEN` y listo.
El token queda guardado sólo en ese navegador; *Salir* lo borra.

## Paso 10 · Qué esperar los primeros días

| Momento | Qué pasa |
|---|---|
| Minuto 1 | Primer escaneo completo. Alertas por Telegram si hay señales fuertes. |
| Cada 15 / 60 min | Escaneo rápido y completo. Se guardan todas las señales. |
| 09:02 (hora local) | Informe diario por Telegram. |
| **72 h** | Primeras señales evaluadas: el dashboard empieza a mostrar el **% de efectividad**. |
| ~1 semana | Ya hay datos útiles. **Activá el modo simulado** desde el dashboard para medir también la operatoria. |
| 3–4 semanas | El nivel de confianza muestra si el agente está listo para considerar el modo real. |

## Paso 11 · Actualizar el agente

Cada vez que haya cambios en la rama desplegada: Coolify → recurso → **Redeploy**.
La base de datos vive en el volumen `agent-storage` y **no se pierde** entre despliegues.

Para que se actualice solo, en **Configuration → Webhooks** Coolify te da una URL para cargar en
GitHub → *Settings → Webhooks* (evento *push*).

## Paso 12 · Backups

- El agente hace una copia diaria de la base (03:17) y conserva 7 días en `/app/storage/backups`, dentro del volumen.
- Para sacar una copia del servidor, por SSH:
  ```bash
  ssh root@187.127.49.189
  docker volume ls | grep agent-storage          # Coolify antepone un prefijo al nombre
  docker run --rm -v <volumen>:/data -v /root:/out alpine \
      sh -c 'cp /data/backups/*.db /out/'
  scp root@187.127.49.189:/root/cryptoagent-*.db .   # desde tu PC
  ```
- Tu plan de Hostinger hace un backup semanal del VPS completo. Si vas a operar real, conviene activar el diario.

## Alternativa: sin Coolify, por SSH

```bash
ssh root@187.127.49.189
git clone -b main https://github.com/apinett/Asistente-ia.git
cd Asistente-ia/crypto-agent
cp .env.example .env && nano .env                # completar las variables del paso 5
sed -i 's|    # ports:|    ports:|; s|    #   - "127.0.0.1:8080:8000"|      - "127.0.0.1:8080:8000"|' docker-compose.yml
docker compose up -d --build
docker compose exec crypto-agent python -m cryptoagent doctor
```

Queda escuchando en `127.0.0.1:8080`, accesible sólo desde el propio servidor. Para verlo desde tu PC sin
exponerlo: `ssh -L 8080:127.0.0.1:8080 root@187.127.49.189` y abrí `http://localhost:8080/dashboard`.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `doctor`: Exchange spot ✖ con `451` o `403` | Bloqueo geográfico del exchange | No debería pasar desde Brasil. Si pasa, cambiá `exchange.spot`/`derivatives` en `config/settings.yaml` (ej. `bybit`). |
| `doctor`: Telegram ✖ con `chat not found` | No le escribiste primero a tu bot, o el chat id está mal | Mandale un mensaje al bot y revisá `TELEGRAM_CHAT_ID`. |
| Deploy falla con `API_TOKEN` | Variable no cargada | Paso 5. |
| El dashboard dice "Token inválido" | El token del navegador no coincide con `API_TOKEN` | Copiá el valor exacto (sin espacios). |
| El dashboard abre pero sin efectividad | Todavía no pasaron 72 h desde el primer escaneo | Esperar: "Pendientes de evaluar" muestra cuántas faltan. |
| El dominio no carga o da error de certificado | DNS sin propagar o puertos 80/443 cerrados | Verificá el registro A y el firewall (paso 2). Después, *Redeploy*. |
| Contenedor reiniciándose | Error de arranque | Coolify → **Logs**. Buscá la primera línea con `ERROR`. |
