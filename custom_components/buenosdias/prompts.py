"""Prompt templates for the good-morning script generation."""

from __future__ import annotations

import json
from datetime import datetime

DEFAULT_PERSONA = "You are the host of a morning radio show, warm and natural."


def build_system_prompt(persona: str) -> str:
    """Return the radio host system prompt."""
    base = (persona or "").strip() or DEFAULT_PERSONA
    return (
        f"{base}\n\n"
        "Write a spoken good-morning script for the user's wake-up based on "
        "the context provided.\n"
        "Rules:\n"
        "- Respond only with the spoken text: no markdown, no tags, no "
        "headings or lists.\n"
        "- Greet briefly and walk through the context sections that have "
        "content, in a natural order.\n"
        "- Use short sentences meant to be read aloud.\n"
        "- Do not invent facts that are not present in the context."
    )


def build_user_prompt(context: dict) -> str:
    """Serialize the context as JSON in the user prompt."""
    now = datetime.now()
    header = f"Today is {now.strftime('%A, %B %d, %Y')}."
    return (
        f"{header}\n\n"
        "Context available (JSON):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Write the good-morning script."
    )
