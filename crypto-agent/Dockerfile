FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CONFIG_PATH=/app/config/settings.yaml \
    DATABASE_URL=sqlite:////app/storage/cryptoagent.db

WORKDIR /app

# TA-Lib >= 0.6 publica wheels manylinux con la librería C incluida: no hace falta compilar
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml .
COPY src ./src
COPY config ./config
RUN pip install --no-deps . \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /app/storage \
    && chown -R agent:agent /app/storage

USER agent
VOLUME ["/app/storage"]
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200 else 1)"

CMD ["python", "-m", "cryptoagent", "serve"]
