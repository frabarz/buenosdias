"""Playback of the script via TTS on the configured media_player.

:func:`async_speak` ensures the ``media_player`` is on (if it advertises
``TURN_ON``), sets ``volume_level``, calls ``tts.speak`` with
``blocking=True``, and restores the previous volume when
``restore_volume`` is enabled.

:func:`async_preload` warms the Home Assistant TTS file + memory cache
silently (no ``media_player`` playback) so the subsequent
``tts.speak`` at alarm time is a cache hit. It mirrors the
``POST /api/tts_get_url`` path: ``SpeechManager.async_cache_message_in_memory``
(``homeassistant/components/tts/__init__.py:939``) which hashes
``sha1(message)+language+options+engine`` and populates
``mem_cache``/``file_cache`` via the ``/api/tts_proxy/{token}`` streaming
path.
"""

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


async def async_preload(hass: HomeAssistant, config: dict, text: str) -> None:
    """Warm the TTS cache for *text* without audible playback.

    Uses ``SpeechManager.async_cache_message_in_memory`` when available
    (the path behind ``POST /api/tts_get_url``). This hashes the message
    + language + options + engine and populates both the in-memory and
    file caches so the later ``async_speak`` (which goes through
    ``generate_media_source_id`` / ``/api/tts_proxy/{token}``) is instant.

    Falls back to creating a ``ResultStream`` and calling
    ``async_set_message`` when the manager helper is not available.
    Never raises - preload failures are logged at debug and ignored.
    """
    if not text or not text.strip():
        return
    tts_cfg = config.get(CONF_TTS, {})
    tts_entity = tts_cfg.get(CONF_ENTITY_ID)
    if not tts_entity:
        _LOGGER.debug("preload skipped: no tts.entity_id configured")
        return
    language = tts_cfg.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    # Try the direct manager cache path (silent, no media_player).
    try:
        from homeassistant.components.tts.const import DATA_TTS_MANAGER

        manager = hass.data.get(DATA_TTS_MANAGER) if hasattr(hass, "data") else None
        if manager is not None:
            try:
                from homeassistant.components.tts.helper import get_engine_instance
            except ImportError:
                get_engine_instance = None  # type: ignore[assignment]
            engine_instance = None
            if get_engine_instance is not None:
                try:
                    engine_instance = get_engine_instance(hass, tts_entity)
                except Exception:
                    engine_instance = None
            if engine_instance is not None:
                try:
                    # Validate/normalize language+options like HA does for speak.
                    lang, options = manager.process_options(
                        engine_instance, language, {}
                    )
                    manager.async_cache_message_in_memory(
                        engine=tts_entity,
                        message=text,
                        use_file_cache=True,
                        language=lang,
                        options=options,
                    )
                    _LOGGER.debug(
                        "TTs cache warmed via SpeechManager for %s (%s chars)",
                        tts_entity,
                        len(text),
                    )
                    return
                except Exception as err:
                    _LOGGER.debug("SpeechManager preload failed, falling back: %s", err)
            # Fallback via ResultStream (mirrors POST /api/tts_get_url)
            try:
                stream = manager.async_create_result_stream(
                    engine=tts_entity,
                    use_file_cache=True,
                    language=language,
                    options={},
                )
                stream.async_set_message(text)
                _LOGGER.debug(
                    "TTs cache warmed via ResultStream for %s (%s chars)",
                    tts_entity,
                    len(text),
                )
                return
            except Exception as err:
                _LOGGER.debug("ResultStream preload failed: %s", err)
    except Exception as err:
        _LOGGER.debug("preload manager unavailable: %s", err)

    # Last resort: no manager (unit tests / early startup) - nothing to warm.
    _LOGGER.debug("preload: no TTS manager, skipping silent warm for %s", tts_entity)
