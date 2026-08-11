"""Orquestación del pipeline completo del buenos días."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from . import script, sources
from .speak import SpeakError, async_speak

_LOGGER = logging.getLogger(__name__)


class PipelineError(Exception):
    """Error en el pipeline del buenos días."""


async def async_run(
    hass: HomeAssistant, config: dict, emit: bool = True
) -> dict:
    """Ejecuta el pipeline: contexto → guion → TTS.

    Con ``emit=False`` genera el guion sin emitir audio (dry-run).
    """
    context = await sources.async_gather_context(hass, config)
    try:
        script_text = await script.async_generate_script(hass, config, context)
    except Exception as err:
        raise PipelineError(f"generación del guion falló: {err}") from err

    if emit:
        try:
            await async_speak(hass, config, script_text)
        except SpeakError as err:
            raise PipelineError(f"emisión del guion falló: {err}") from err

    return {"script": script_text, "context": context}
