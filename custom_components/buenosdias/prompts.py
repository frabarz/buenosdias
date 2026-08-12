"""Plantillas de prompts para la generación del guion del buenos días."""

from __future__ import annotations

import json
from datetime import datetime

DEFAULT_PERSONA = "Eres el locutor de una radio matutina en español latinoamericano, cercano y natural."


def build_system_prompt(persona: str) -> str:
    """Devuelve el system prompt del locutor de radio."""
    base = (persona or "").strip() or DEFAULT_PERSONA
    return (
        f"{base}\n\n"
        "Escribe un guion hablado para el despertar del usuario a partir del "
        "contexto que se te proporciona.\n"
        "Normas:\n"
        "- Responde únicamente con el texto hablado: sin markdown, sin "
        "etiquetas, sin encabezados ni listas.\n"
        "- Saluda brevemente y repasa las secciones del contexto que tengan "
        "contenido, en un orden natural.\n"
        "- Usa frases cortas pensadas para leerse en voz alta.\n"
        "- No inventes datos que no aparezcan en el contexto."
    )


def build_user_prompt(context: dict) -> str:
    """Serializa el contexto como JSON en el prompt de usuario."""
    now = datetime.now()
    header = f"Hoy es {now.strftime('%A %d de %B de %Y')}."
    return (
        f"{header}\n\n"
        "Contexto disponible (JSON):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Redacta el guion del buenos días."
    )
