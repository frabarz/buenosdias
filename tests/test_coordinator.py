"""Tests of the full pipeline (context → script → TTS)."""

import asyncio

import pytest

from custom_components.buenosdias import coordinator, script
from custom_components.buenosdias.const import CONF_SOURCES, CONF_WEATHER
from custom_components.buenosdias.coordinator import PipelineError
from custom_components.buenosdias.llm import LLMClient
from custom_components.buenosdias.speak import SpeakError


class _FixedLLM(LLMClient):
    async def async_complete(self, system, user):
        return "Good morning, it is sunny today."


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


def test_async_run_generates_and_plays(monkeypatch):
    spoken = {}

    async def fake_speak(hass, config, text):
        spoken["text"] = text

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    result = _run(coordinator.async_run(_make_hass(), _config()))
    assert result["script"] == "Good morning, it is sunny today."
    assert spoken["text"] == "Good morning, it is sunny today."


def test_async_run_emit_false_does_not_play(monkeypatch):
    spoken = []

    async def fake_speak(hass, config, text):
        spoken.append(text)

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    result = _run(coordinator.async_run(_make_hass(), _config(), emit=False))
    assert result["script"] == "Good morning, it is sunny today."
    assert spoken == []


def test_async_run_speak_failure_raises_pipeline_error(monkeypatch):
    async def fake_speak(hass, config, text):
        raise SpeakError("tts broken")

    monkeypatch.setattr(coordinator, "async_speak", fake_speak)
    monkeypatch.setattr(script, "build_llm", lambda hass, config: _FixedLLM())

    with pytest.raises(PipelineError):
        _run(coordinator.async_run(_make_hass(), _config()))


def test_async_run_script_failure_raises_pipeline_error(monkeypatch):
    async def bad_complete(system, user):
        raise RuntimeError("llm down")

    class _BadLLM(LLMClient):
        async def async_complete(self, system, user):
            return await bad_complete(system, user)

    monkeypatch.setattr(script, "build_llm", lambda hass, config: _BadLLM())

    with pytest.raises(PipelineError):
        _run(coordinator.async_run(_make_hass(), _config()))
