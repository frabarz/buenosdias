"""Playback of the script via TTS on the configured media_player."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaPlayerEntityFeature

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
    """Error playing the script via TTS."""


def media_player_volume(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return the media_player's current volume level, or None if unknown."""
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
    """Call an HA service blocking, translating errors into SpeakError."""
    try:
        await hass.services.async_call(domain, service, data, blocking=True)
    except Exception as err:
        msg = f"{domain}.{service} failed: {err}"
        raise SpeakError(msg) from err


async def async_speak(hass: HomeAssistant, config: dict, text: str) -> None:
    """Play `text` via TTS on the configured media_player."""
    tts_cfg = config.get(CONF_TTS, {})
    tts_entity = tts_cfg.get(CONF_ENTITY_ID)
    media_player = tts_cfg.get(CONF_MEDIA_PLAYER)
    if not tts_entity or not media_player:
        msg = "tts.entity_id and tts.media_player are required"
        raise SpeakError(msg)

    language = tts_cfg.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    volume = tts_cfg.get(CONF_VOLUME, DEFAULT_VOLUME)
    restore_volume = tts_cfg.get(CONF_RESTORE_VOLUME, True)
    previous_volume = media_player_volume(hass, media_player)

    state = hass.states.get(media_player)
    supports_turn_on = False
    if state is not None:
        turn_on_flag = int(state.attributes.get("supported_features") or 0)
        supports_turn_on = bool(turn_on_flag & MediaPlayerEntityFeature.TURN_ON)
    if state is None or (
        supports_turn_on and state.state in ("off", "standby", "idle")
    ):
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
