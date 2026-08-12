"""Emisión del guion por TTS sobre el media_player configurado."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import (
    CONF_ENTITY_ID,
    CONF_LANGUAGE,
    CONF_MEDIA_PLAYER,
    CONF_RESTORE_VOLUME,
    CONF_TTS,
    CONF_VOLUME,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "es-ES"
DEFAULT_VOLUME = 0.6


class SpeakError(Exception):
    """Error al emitir el guion por TTS."""


def media_player_volume(hass: HomeAssistant, entity_id: str) -> float | None:
    """Devuelve el volumen actual del media_player, o None si no se conoce."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get("volume_level")


async def _call(
    hass: HomeAssistant,
    domain: str,
    service: str,
    data: dict,
) -> None:
    """Invoca un servicio de HA en bloque, traduciendo errores a SpeakError."""
    try:
        await hass.services.async_call(domain, service, data, blocking=True)
    except Exception as err:
        msg = f"{domain}.{service} falló: {err}"
        raise SpeakError(msg) from err


async def async_speak(hass: HomeAssistant, config: dict, text: str) -> None:
    """Reproduce `text` por TTS en el media_player configurado."""
    tts_cfg = config.get(CONF_TTS, {})
    tts_entity = tts_cfg.get(CONF_ENTITY_ID)
    media_player = tts_cfg.get(CONF_MEDIA_PLAYER)
    if not tts_entity or not media_player:
        msg = "tts.entity_id y tts.media_player son obligatorios"
        raise SpeakError(msg)

    language = tts_cfg.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    volume = tts_cfg.get(CONF_VOLUME, DEFAULT_VOLUME)
    restore_volume = tts_cfg.get(CONF_RESTORE_VOLUME, True)
    previous_volume = media_player_volume(hass, media_player)

    state = hass.states.get(media_player)
    if state is None or state.state in ("off", "standby", "idle"):
        await _call(hass, "media_player", "turn_on", {"entity_id": media_player})

    if previous_volume is None or previous_volume != volume:
        await _call(
            hass,
            "media_player",
            "volume_set",
            {"entity_id": media_player, "volume_level": volume},
        )

    await _call(
        hass,
        "tts",
        "speak",
        {
            "entity_id": tts_entity,
            "media_player_entity_id": media_player,
            "message": text,
            "language": language,
        },
    )

    if restore_volume and previous_volume is not None and previous_volume != volume:
        await _call(
            hass,
            "media_player",
            "volume_set",
            {"entity_id": media_player, "volume_level": previous_volume},
        )
