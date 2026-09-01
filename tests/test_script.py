"""Tests of the script generation and validation."""

import asyncio

import pytest

from custom_components.buenosdias import prompts, script
from custom_components.buenosdias.llm import LLMClient, LLMError


class _FixedLLM(LLMClient):
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def async_complete(self, system, user):
        self.calls += 1
        return self.text


def _run(coro):
    return asyncio.run(coro)


def test_validate_script_ok():
    assert script.validate_script("  Good morning.  ", 2000) == "Good morning."


def test_validate_script_empty():
    with pytest.raises(ValueError):
        script.validate_script("   ", 2000)


def test_validate_script_too_long():
    with pytest.raises(ValueError):
        script.validate_script("a" * 100, max_chars=50)


def test_validate_script_too_long_error_carries_text():
    with pytest.raises(script.ScriptTooLongError) as excinfo:
        script.validate_script("a" * 100, max_chars=50)
    assert excinfo.value.length == 100
    assert excinfo.value.max_chars == 50
    assert excinfo.value.text == "a" * 100
    assert excinfo.type is script.ScriptTooLongError


@pytest.mark.parametrize(
    "bad",
    ["```code```", "# Title", "**bold**", "__italic__", "- list"],
)
def test_validate_script_rejects_markdown(bad):
    with pytest.raises(ValueError):
        script.validate_script(bad, 2000)


def test_async_generate_script_returns_text():
    llm = _FixedLLM("Good morning, it is sunny.")
    out = _run(script.async_generate_script(None, {}, {"weather": {}}, llm=llm))
    assert out == "Good morning, it is sunny."
    assert llm.calls == 1


def test_async_generate_script_retries_and_exhausts():
    llm = _FixedLLM("```markdown```")
    with pytest.raises(LLMError):
        _run(script.async_generate_script(None, {}, {}, llm=llm))
    assert llm.calls == script.MAX_ATTEMPTS


def test_async_generate_script_applies_max_chars():
    llm = _FixedLLM("a" * 500)
    config = {script.CONF_LLM: {script.CONF_MAX_CHARS: 100}}
    with pytest.raises(LLMError):
        _run(script.async_generate_script(None, config, {}, llm=llm))


class _RecordingLLM(LLMClient):
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0
        self.requests = []

    async def async_complete(self, system, user):
        self.calls += 1
        self.requests.append((system, user))
        return self.results[min(self.calls - 1, len(self.results) - 1)]


def test_async_generate_script_retries_with_condense_prompt():
    llm = _RecordingLLM([("a" * 100), "Good morning, refined."])
    config = {script.CONF_LLM: {script.CONF_MAX_CHARS: 50}}
    out = _run(script.async_generate_script(None, config, {"weather": {}}, llm=llm))
    assert out == "Good morning, refined."
    assert llm.calls == 2
    first_user, second_user = (u for _, u in llm.requests)
    assert "Write the good-morning script." in first_user
    assert "MUST be at most 50 characters" in second_user
    assert "a" * 100 in second_user


def test_async_generate_script_exhausts_on_repeated_overflow():
    llm = _RecordingLLM(["a" * 100, "a" * 100])
    config = {script.CONF_LLM: {script.CONF_MAX_CHARS: 50}}
    with pytest.raises(LLMError):
        _run(script.async_generate_script(None, config, {}, llm=llm))
    assert llm.calls == script.MAX_ATTEMPTS
    assert "MUST be at most 50 characters" in llm.requests[1][1]


def test_build_user_prompt_serializes_context():
    context = {"weather": {"weather.casa": {"state": "sunny"}}}
    user = prompts.build_user_prompt(context)
    assert "weather.casa" in user
    assert "sunny" in user


def test_build_system_prompt_includes_rules():
    system = prompts.build_system_prompt("")
    assert "markdown" in system
    assert "spoken text" in system


def test_build_system_prompt_uses_persona():
    system = prompts.build_system_prompt("You are a very serious radio host.")
    assert "radio host" in system
