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


def build_condense_prompt(context: dict, previous_text: str, max_chars: int) -> str:
    """Build a retry prompt asking the LLM to recompose an over-long script."""
    return (
        "You keep writing the spoken good-morning script for the morning radio show.\n"
        "The script you just wrote is too long to be spoken comfortably, so "
        "rewrite it more concisely while keeping it natural to read aloud.\n\n"
        f"Limit: your script MUST be at most {max_chars} characters (the current "
        f"draft is {len(previous_text)} characters).\n"
        "Cover the same context sections but more briefly, keeping the greeting "
        "and a natural spoken flow. Do not invent facts that are not in the context.\n"
        "Rules:\n"
        "- Respect the original language of the script.\n"
        "- Respond only with the spoken text: no markdown, no tags, no headings "
        "or lists.\n"
        f"- Do not exceed {max_chars} characters.\n"
        "- If space is tight you may drop some news items; keep the important or "
        "the positive ones, so the listener starts their day with relevant info and "
        "in a good mood.\n\n"
        "Context available (JSON):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Current draft to condense (do not repeat it verbatim):\n"
        f"{previous_text}\n"
    )
