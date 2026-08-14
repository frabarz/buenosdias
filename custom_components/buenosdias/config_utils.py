"""Assemble the runtime configuration from a config entry's data and options."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from .config_schema import BUENOSDIAS_SCHEMA
from .const import (
    CONF_LLM,
    CONF_OPENAI,
    CONF_PERSONA,
    CONF_SCHEDULE,
    CONF_SOURCES,
    CONF_TTS,
)

_LOGGER = logging.getLogger(__name__)


def build_config(data: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, Any]:
    """Build the nested configuration dict consumed by the runtime modules.

    Connection settings (LLM credentials and endpoint) come from ``data``;
    behavioral settings come from ``options``. ``options`` never holds the
    API key, so ``data`` wins on conflicts for the OpenAI section.
    """
    llm = dict(data.get(CONF_LLM, {}))
    for key, value in options.get(CONF_LLM, {}).items():
        if key != CONF_OPENAI:
            llm[key] = value

    openai = dict(options.get(CONF_LLM, {}).get(CONF_OPENAI, {}))
    openai.update(data.get(CONF_LLM, {}).get(CONF_OPENAI, {}))
    llm[CONF_OPENAI] = openai

    config: dict[str, Any] = {
        CONF_LLM: llm,
        CONF_TTS: dict(options.get(CONF_TTS, {})),
        CONF_SOURCES: dict(options.get(CONF_SOURCES, {})),
        CONF_SCHEDULE: dict(options.get(CONF_SCHEDULE, {})),
        CONF_PERSONA: options.get(CONF_PERSONA, ""),
    }

    try:
        return dict(BUENOSDIAS_SCHEMA(config))
    except vol.Invalid:
        # A single malformed option must not prevent setup; fall back to the
        # raw merged config so the rest of the integration keeps working.
        _LOGGER.warning("Invalid buenosdias options, using them as-is")
        return config