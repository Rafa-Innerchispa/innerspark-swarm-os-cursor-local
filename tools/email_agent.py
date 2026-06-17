"""Clasificación de importancia y alertas WhatsApp."""

from __future__ import annotations

import re
from typing import Any


def keyword_importance(subject: str, snippet: str, keywords: list[str]) -> str | None:
    text = f"{subject} {snippet}".lower()
    for kw in keywords:
        if kw.lower() in text:
            return "alta"
    return None


def classify_importance(
    subject: str,
    snippet: str,
    from_addr: str,
    keywords: list[str],
) -> dict[str, Any]:
    """Reglas rápidas + Ollama si hace falta."""
    kw_hit = keyword_importance(subject, snippet, keywords)
    if kw_hit:
        return {"importance": kw_hit, "reason": "palabra clave", "source": "rules"}

    urgent = re.search(r"urgente|asap|inmediat|vencid|factura|pago|deuda|reclamo|falla|caído|caido", f"{subject} {snippet}", re.I)
    if urgent:
        return {"importance": "alta", "reason": urgent.group(0), "source": "rules"}

    from tools.ollama_chat import ollama_available, ollama_chat

    if not ollama_available():
        return {"importance": "normal", "reason": "sin clasificador", "source": "default"}

    try:
        raw = ollama_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Clasificas correos para PC Doctor Ecuador. Responde SOLO una palabra: "
                        "alta, normal o baja. Alta = requiere acción pronto (cliente, pago, falla, legal)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"De: {from_addr}\nAsunto: {subject}\n{texto_resumen(snippet)}",
                },
            ],
            temperature=0.1,
            timeout=60,
        )
        level = raw.strip().lower().split()[0] if raw else "normal"
        if level not in {"alta", "normal", "baja"}:
            level = "normal"
        return {"importance": level, "reason": "análisis IA", "source": "ollama"}
    except Exception as e:
        return {"importance": "normal", "reason": str(e), "source": "error"}


def texto_resumen(snippet: str) -> str:
    return snippet[:500] if snippet else "(sin cuerpo)"


def format_whatsapp_alert(account: str, subject: str, from_addr: str, importance: str, reason: str) -> str:
    return (
        f"📧 Ralphi IA — correo {importance.upper()}\n"
        f"Cuenta: {account}\n"
        f"De: {from_addr}\n"
        f"Asunto: {subject}\n"
        f"Motivo: {reason}"
    )
