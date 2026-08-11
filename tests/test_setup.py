"""Tests de arranque de la integración (async_setup) y del manifest."""

import asyncio
import json
from pathlib import Path

from custom_components.buenosdias import DOMAIN, async_setup

MANIFEST = Path(__file__).parent.parent / "custom_components/buenosdias/manifest.json"


def test_manifest_valido():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["version"]
    assert manifest["config_flow"] is False
    assert manifest["integration_type"] == "service"
    assert manifest["homeassistant"] == "2025.2.0"


def test_async_setup_registra_servicio_context(fake_hass):
    hass, registered = fake_hass()
    asyncio.run(async_setup(hass, {DOMAIN: {"sources": {}}}))
    assert (DOMAIN, "context") in registered
    assert hass.data[DOMAIN]["config"] == {"sources": {}}


def test_async_setup_registra_servicio_generate(fake_hass):
    hass, registered = fake_hass()
    asyncio.run(async_setup(hass, {DOMAIN: {}}))
    assert (DOMAIN, "generate") in registered


def test_async_setup_devuelve_true(fake_hass):
    hass, _ = fake_hass()
    assert asyncio.run(async_setup(hass, {DOMAIN: {}})) is True


def test_servicio_context_devuelve_contexto(fake_hass):
    from conftest import FakeState

    hass, registered = fake_hass(
        {"weather.casa": FakeState("sunny", {"temperature": 21.5})}
    )
    asyncio.run(
        async_setup(
            hass,
            {DOMAIN: {"sources": {"weather": ["weather.casa"]}}},
        )
    )
    handler = registered[(DOMAIN, "context")]
    result = asyncio.run(handler(None))
    assert result["weather"]["weather.casa"]["state"] == "sunny"
    assert "timestamp" in result


def test_servicio_generate_devuelve_guion(fake_hass, monkeypatch):
    from custom_components.buenosdias import script

    class FakeLLM:
        async def async_complete(self, system, user):
            return "Buenos días, hoy hace sol."

    def fake_build(hass, config):
        return FakeLLM()

    monkeypatch.setattr(script, "build_llm", fake_build)

    hass, registered = fake_hass()
    asyncio.run(async_setup(hass, {DOMAIN: {}}))
    handler = registered[(DOMAIN, "generate")]
    result = asyncio.run(handler(None))
    assert result["script"] == "Buenos días, hoy hace sol."
