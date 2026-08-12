"""Orchestration of the full good-morning pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import script, sources
from .speak import SpeakError, async_speak

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PipelineError(Exception):
    """Error in the good-morning pipeline."""


async def async_run(
    hass: HomeAssistant,
    config: dict,
    emit: bool = True,
) -> dict:
    """Run the pipeline: context → script → TTS.

    With ``emit=False`` it generates the script without playing audio (dry-run).
    """
    context = await sources.async_gather_context(hass, config)
    try:
        script_text = await script.async_generate_script(hass, config, context)
    except Exception as err:
        msg = f"script generation failed: {err}"
        raise PipelineError(msg) from err

    if emit:
        try:
            await async_speak(hass, config, script_text)
        except SpeakError as err:
            msg = f"script playback failed: {err}"
            raise PipelineError(msg) from err

    return {"script": script_text, "context": context}
