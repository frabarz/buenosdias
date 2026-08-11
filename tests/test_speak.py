"""Tests de la emisión del guion por TTS."""

import asyncio

import pytest

from custom_components.buenosdias import speak
from custom_components.buenosdias.const import CONF_SOURCES, CONF_TTS


def _run(coro):
    return asyncio.run(coro)


def _config(**tts):
    cfg = {
        CONF_TTS: {
            "entity_id": "tts.piper",
            "media_player": "media_player.sala",
            "language": "es-ES",
            "volume": 0.6,
            "restore_volume": True,
        }
    }
    cfg[CONF_TTS].update(tts)
    return cfg


def _mp_state(state="on", volume=0.8):
    from conftest import FakeState

    return FakeState(state, {"volume_level": volume})


def test_async_speak_llama_y_restaura_volumen(fake_hass):
    hass, _ = fake_hass(
        {"media_player.sala": _mp_state(state="on", volume=0.8)}
    )
    _run(speak.async_speak(hass, _config(), "Buenos días."))

    assert (("media_player", "volume_set", {"entity_id": "media_player.sala", "volume_level": 0.6})) in hass.calls
    tts_call = next(c for c in hass.calls if c[0] == "tts")
    assert tts_call[1] == "speak"
    assert tts_call[2]["message"] == "Buenos días."
    assert tts_call[2]["language"] == "es-ES"
    assert tts_call[2]["entity_id"] == "tts.piper"
    assert tts_call[2]["media_player_entity_id"] == "media_player.sala"
    assert hass.calls[-1] == (
        "media_player",
        "volume_set",
        {"entity_id": "media_player.sala", "volume_level": 0.8},
    )


def test_async_speak_enciende_media_player_apagado(fake_hass):
    hass, _ = fake_hass({"media_player.sala": _mp_state(state="off", volume=0.8)})
    _run(speak.async_speak(hass, _config(), "Hola"))
    assert ("media_player", "turn_on", {"entity_id": "media_player.sala"}) in hass.calls


def test_async_speak_no_enciende_si_esta_encendido(fake_hass):
    hass, _ = fake_hass({"media_player.sala": _mp_state(state="on", volume=0.8)})
    _run(speak.async_speak(hass, _config(), "Hola"))
    assert not any(c[1] == "turn_on" for c in hass.calls)


def test_async_speak_no_restaura_si_restore_false(fake_hass):
    hass, _ = fake_hass({"media_player.sala": _mp_state(state="on", volume=0.8)})
    _run(speak.async_speak(hass, _config(restore_volume=False), "Hola"))
    assert not any(
        c[1] == "volume_set" and c[2]["volume_level"] == 0.8 for c in hass.calls
    )


def test_async_speak_omite_volumen_si_ya_coincide(fake_hass):
    hass, _ = fake_hass({"media_player.sala": _mp_state(state="on", volume=0.6)})
    _run(speak.async_speak(hass, _config(), "Hola"))
    assert not any(
        c[1] == "volume_set" and c[2]["volume_level"] == 0.6 for c in hass.calls
    )


def test_async_speak_requiere_entity_y_media_player(fake_hass):
    hass, _ = fake_hass()
    with pytest.raises(speak.SpeakError):
        _run(speak.async_speak(hass, {CONF_TTS: {}}, "Hola"))


def test_async_speak_error_de_servicio(fake_hass, monkeypatch):
    hass, _ = fake_hass({"media_player.sala": _mp_state(state="off")})

    async def fail_call(domain, service, data=None, blocking=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(hass.services, "async_call", fail_call)
    with pytest.raises(speak.SpeakError):
        _run(speak.async_speak(hass, _config(), "Hola"))


def test_media_player_volume_desconocido_es_none(fake_hass):
    hass, _ = fake_hass()
    assert speak.media_player_volume(hass, "media_player.sala") is None
