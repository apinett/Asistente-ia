"""Envío a Telegram con una llamada HTTP directa a la Bot API.

python-telegram-bot (~29k ⭐) es excelente para bots conversacionales, pero acá sólo
necesitamos `sendMessage`: una función con httpx evita una dependencia pesada.
"""

from __future__ import annotations

import html
import logging

import httpx

log = logging.getLogger(__name__)
MAX_LEN = 4000  # límite de Telegram: 4096


def _chunks(text: str, size: int = MAX_LEN) -> list[str]:
    parts, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > size and cur:
            parts.append(cur)
            cur = ""
        cur += line
    if cur:
        parts.append(cur)
    return parts


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token, self.chat_id = token, chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str, preformatted_html: bool = False) -> bool:
        if not self.enabled:
            log.debug("Telegram deshabilitado; mensaje:\n%s", text)
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = text if preformatted_html else html.escape(text)
        ok = True
        async with httpx.AsyncClient(timeout=20) as client:
            for chunk in _chunks(body):
                try:
                    r = await client.post(
                        url,
                        json={"chat_id": self.chat_id, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True},
                    )
                    r.raise_for_status()
                except httpx.HTTPError as exc:
                    log.warning("Telegram falló: %s", exc)
                    ok = False
        return ok
