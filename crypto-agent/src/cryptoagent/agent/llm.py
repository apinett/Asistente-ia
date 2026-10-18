"""Narrativa del informe diario con Claude.

Claude no calcula nada: recibe el JSON ya calculado por el motor cuantitativo y lo
convierte en un informe legible, priorizando lo relevante y explicando los riesgos.
Si no hay API key, el agente usa el informe por plantilla (report.py).
"""

from __future__ import annotations

import json
import logging

import anthropic

log = logging.getLogger(__name__)

# Modelos que aceptan el fallback server-side por categoría de rechazo
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

SYSTEM_PROMPT = """Sos el analista jefe de un agente de investigación del mercado cripto. Recibís un JSON con \
los resultados cuantitativos del día: régimen de mercado, amplitud, contexto macro (Fear & Greed, dominancia, \
stablecoins), las señales más fuertes alcistas y bajistas con sus componentes (tendencia, momentum, volumen, \
patrones de velas, estructura, fuerza relativa) y el análisis LPF de posicionamiento en derivados \
(cuadrante precio/open interest, funding y su z-score, flujo spot vs perpetuos, top traders vs retail, riesgo de \
squeeze y mapa estimado de liquidaciones). También recibís el desempeño medido de las señales pasadas.

Redactá el informe diario en español rioplatense, claro y directo, para un trader que lo lee en Telegram:
- Texto plano con emojis sobrios y guiones; nada de Markdown (ni asteriscos, ni numerales, ni tablas).
- Estructura: 1) Panorama del mercado (3-5 líneas). 2) Lectura de derivados/LPF: qué dice el apalancamiento \
sobre la sostenibilidad del movimiento. 3) Oportunidades alcistas destacadas. 4) Debilidades / riesgos bajistas. \
5) Niveles clave de BTC y ETH. 6) Qué vigilar en las próximas 24 h. 7) Desempeño reciente del agente, si hay datos.
- Usá exclusivamente los números del JSON; no inventes precios, niveles ni noticias.
- Cuando las señales técnicas y el posicionamiento se contradicen, decilo explícitamente y explicá cuál pesa más y por qué.
- Expresá probabilidades y escenarios, nunca certezas. Para cada idea, mencioná la invalidación.
- Máximo ~450 palabras. Cerrá con: "No es asesoramiento financiero."
"""


async def write_narrative(context: dict, api_key: str, model: str) -> str | None:
    if not api_key:
        return None
    client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=3)
    payload = json.dumps(context, ensure_ascii=False, default=str)
    kwargs: dict = dict(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": f"Datos del escaneo de hoy (JSON):\n{payload}\n\nRedactá el informe diario."}],
    )
    try:
        if model in FALLBACK_MODELS:
            resp = await client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
            )
        else:
            resp = await client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        log.error("ANTHROPIC_API_KEY inválida: se usa el informe por plantilla")
        return None
    except anthropic.RateLimitError:
        log.warning("Claude con rate limit: se usa el informe por plantilla")
        return None
    except anthropic.APIStatusError as exc:
        log.warning("Claude devolvió %s: %s", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError as exc:
        log.warning("Sin conexión con Claude: %s", exc)
        return None

    if resp.stop_reason == "refusal":
        log.warning("Claude declinó el informe (%s)", getattr(resp.stop_details, "category", None))
        return None
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text or None
