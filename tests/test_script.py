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
