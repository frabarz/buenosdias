"""Tests of the LLM clients."""

import asyncio
from types import SimpleNamespace
from typing import cast

import httpx
import pytest

from custom_components.buenosdias.const import (
    CONF_LLM,
    CONF_OPENAI,
    MODE_OPENAI_COMPATIBLE,
)
from custom_components.buenosdias.llm import (
    LLMClient,
    LLMError,
    FallbackLLM,
    HAConversationLLM,
    OpenAICompatLLM,
    build_llm,
)


def _run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, speech):
        self.speech = speech


class FakeResult:
    def __init__(self, speech):
        self.response = FakeResponse(speech)


class _FailingLLM(LLMClient):
    async def async_complete(self, system, user):
        raise LLMError("primary failure")


class _OkLLM(LLMClient):
    async def async_complete(self, system, user):
        return "ok"


def _patch_conversation(monkeypatch, async_converse):
    monkeypatch.setattr(
        "homeassistant.components.conversation",
        SimpleNamespace(async_converse=async_converse),
        raising=False,
    )


def test_ha_conversation_llm_extracts_text(monkeypatch):
    async def async_converse(**kwargs):
        return FakeResult({"plain": {"speech": "Good morning, everyone."}})

    _patch_conversation(monkeypatch, async_converse)
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    llm = HAConversationLLM(hass)
    text = _run(llm.async_complete("system", "user"))
    assert text == "Good morning, everyone."


def test_ha_conversation_llm_passes_extra_system_prompt_and_agent(monkeypatch):
    captured = {}

    async def async_converse(**kwargs):
        captured.update(kwargs)
        return FakeResult({"plain": {"speech": "hola"}})

    _patch_conversation(monkeypatch, async_converse)
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    llm = HAConversationLLM(hass, agent="conversation.openai")
    _run(llm.async_complete("SYS", "USR"))
    assert captured["extra_system_prompt"] == "SYS"
    assert captured["agent_id"] == "conversation.openai"
    assert captured["text"] == "USR"


def test_ha_conversation_llm_empty_text_is_error(monkeypatch):
    _patch_conversation(monkeypatch, lambda **kwargs: FakeResult({"plain": {}}))
    llm = HAConversationLLM(SimpleNamespace(config=None))
    with pytest.raises(LLMError):
        _run(llm.async_complete("s", "u"))


def test_ha_conversation_llm_agent_error(monkeypatch):
    async def async_converse(**kwargs):
        raise RuntimeError("boom")

    _patch_conversation(monkeypatch, async_converse)
    llm = HAConversationLLM(SimpleNamespace(config=None))
    with pytest.raises(LLMError):
        _run(llm.async_complete("s", "u"))


def test_openai_compat_llm_extracts_content_and_payload():
    import json as json_module

    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        body = json_module.loads(request.read().decode("utf-8"))
        captured["auth"] = request.headers.get("authorization")
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "sys"
        assert body["messages"][1]["role"] == "user"
        assert body["messages"][1]["content"] == "usr"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Script ok"}}]}
        )

    llm = OpenAICompatLLM(
        base_url="http://localhost:11434/v1/",
        api_key="sk-123",
        model="llama3",
        transport=httpx.MockTransport(handler),
    )
    text = _run(llm.async_complete("sys", "usr"))
    assert text == "Script ok"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-123"


def test_openai_compat_llm_sin_api_key():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    llm = OpenAICompatLLM(
        "http://x/v1", "", "m", transport=httpx.MockTransport(handler)
    )
    _run(llm.async_complete("s", "u"))
    assert captured["auth"] is None


def test_openai_compat_llm_invalid_response():
    def handler(request):
        return httpx.Response(200, json={"unexpected": True})

    llm = OpenAICompatLLM(
        "http://x/v1", "", "m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LLMError):
        _run(llm.async_complete("s", "u"))


def test_openai_compat_llm_http_error():
    def handler(request):
        return httpx.Response(500, json={})

    llm = OpenAICompatLLM(
        "http://x/v1", "", "m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LLMError):
        _run(llm.async_complete("s", "u"))


def test_fallback_llm_uses_fallback():
    client = FallbackLLM(_FailingLLM(), _OkLLM())
    assert _run(client.async_complete("s", "u")) == "ok"


def test_fallback_llm_primary_ok_skips_fallback():
    client = FallbackLLM(_OkLLM(), _FailingLLM())
    assert _run(client.async_complete("s", "u")) == "ok"


def test_build_llm_ha_primary(monkeypatch):
    fake_openai = lambda base_url, api_key, model, transport=None: _OkLLM()  # noqa: E731
    fake_ha = lambda hass, agent="": _FailingLLM()  # noqa: E731
    monkeypatch.setattr("custom_components.buenosdias.llm.OpenAICompatLLM", fake_openai)
    monkeypatch.setattr("custom_components.buenosdias.llm.HAConversationLLM", fake_ha)

    config = {CONF_LLM: {CONF_OPENAI: {"base_url": "http://x/v1"}}}
    client = cast(FallbackLLM, build_llm(None, config))
    assert isinstance(client, FallbackLLM)
    assert isinstance(client.primary, _FailingLLM)
    assert isinstance(client.fallback, _OkLLM)


def test_build_llm_openai_primary(monkeypatch):
    fake_openai = lambda base_url, api_key, model, transport=None: _OkLLM()  # noqa: E731
    fake_ha = lambda hass, agent="": _FailingLLM()  # noqa: E731
    monkeypatch.setattr("custom_components.buenosdias.llm.OpenAICompatLLM", fake_openai)
    monkeypatch.setattr("custom_components.buenosdias.llm.HAConversationLLM", fake_ha)

    config = {
        CONF_LLM: {
            "mode": MODE_OPENAI_COMPATIBLE,
            CONF_OPENAI: {"base_url": "http://x/v1"},
        }
    }
    client = cast(FallbackLLM, build_llm(None, config))
    assert isinstance(client.primary, _OkLLM)
    assert isinstance(client.fallback, _FailingLLM)
