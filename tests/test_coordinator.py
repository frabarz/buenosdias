"""Tests del pipeline completo (contexto → guion → TTS)."""

import asyncio

import pytest

from custom_components.buenosdias import coordinator, script
from custom_components.buenosdias.const import CONF_SOURCES, CONF_WEATHER
from custom_components.buenosdias.coordinator import PipelineError
from custom_components.buenosdias.llm import LLMClient
from custom_components.buenosdias.speak import SpeakError


class _FixedLLM(LLMClient):
    async def async_complete(self, system, user):
        return "Buenos días, hoy hace sol."


def _run(coro):
    return asyncio.run(coro)


def _make_hass():
    from conftest import FakeState
    from types import SimpleNamespace

    states = {"weather.casa": FakeState("sunny", {"temperature": 21.5})}
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: states.get(eid)),
        services=SimpleNamespace(async_call=lambda *a, **k: None),
    )


def _config():
    return {CONF_SOURCES: {CONF_WEATHER: ["weather.casa"]}}


def test_async_run_genera_y_emite(monkeypatch):
    spoken = {}

    async def fake_speak(hass, config, text):
        spoken["text"] = text

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    result = _run(coordinator.async_run(_make_hass(), _config()))
    assert result["script"] == "Buenos días, hoy hace sol."
    assert spoken["text"] == "Buenos días, hoy hace sol."


def test_async_run_emit_false_no_emite(monkeypatch):
    spoken = []

    async def fake_speak(hass, config, text):
        spoken.append(text)

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    result = _run(coordinator.async_run(_make_hass(), _config(), emit=False))
    assert result["script"] == "Buenos días, hoy hace sol."
    assert spoken == []


def test_async_run_falla_speak_levanta_pipeline_error(monkeypatch):
    async def fake_speak(hass, config, text):
        raise SpeakError("tts roto")

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    with pytest.raises(PipelineError):
        _run(coordinator.async_run(_make_hass(), _config()))


def test_async_run_falla_guion_levanta_pipeline_error(monkeypatch):
    async def bad_complete(system, user):
        raise RuntimeError("llm caído")

    class _BadLLM(LLMClient):
        async def async_complete(self, system, user):
            return await bad_complete(system, user)

    monkeypatch.setattr(script, "build_llm", lambda hass, config: _BadLLM())

    with pytest.raises(PipelineError):
        _run(coordinator.async_run(_make_hass(), _config()))
