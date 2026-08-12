"""Generación y validación del guion del buenos días."""

from __future__ import annotations

import logging
import re
from typing import Any

from . import prompts
from .const import CONF_LLM, CONF_MAX_CHARS, CONF_PERSONA
from .llm import LLMClient, LLMError, build_llm

_LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 2000
MAX_ATTEMPTS = 2

MARKDOWN_BLOCK_RE = re.compile(
    r"```|(^|\n)#{1,6}\s|(\*\*|__)|(^|\n)\s*[-*]\s",
    re.MULTILINE,
)


def validate_script(text: str, max_chars: int) -> str:
    """Valida y normaliza el guion generado."""
    text = (text or "").strip()
    if not text:
        msg = "guion vacío"
        raise ValueError(msg)
    if len(text) > max_chars:
        msg = f"guion demasiado largo ({len(text)} > {max_chars})"
        raise ValueError(msg)
    if MARKDOWN_BLOCK_RE.search(text):
        msg = "el guion contiene bloques markdown"
        raise ValueError(msg)
    return text


async def async_generate_script(
    hass: Any,
    config: dict,
    context: dict,
    llm: LLMClient | None = None,
) -> str:
    """Genera el guion del buenos días con un reintento único."""
    llm_cfg = config.get(CONF_LLM, {})
    max_chars = llm_cfg.get(CONF_MAX_CHARS, DEFAULT_MAX_CHARS)
    client = llm or build_llm(hass, config)
    system = prompts.build_system_prompt(config.get(CONF_PERSONA, ""))
    user = prompts.build_user_prompt(context)

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return validate_script(
                await client.async_complete(system, user),
                max_chars,
            )
        except (LLMError, ValueError) as err:
            last_error = err
            _LOGGER.warning("Intento %s de generación falló: %s", attempt, err)
    msg = f"generación de guion falló: {last_error}"
    raise LLMError(msg)
