"""Tests of the integration setup (async_setup / async_setup_entry) and the manifest."""

import asyncio
import json
from pathlib import Path

from custom_components.buenosdias import DOMAIN, async_setup, async_setup_entry

MANIFEST = Path(__file__).parent.parent / "custom_components/buenosdias/manifest.json"


def test_manifest_valid():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["version"]
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["integration_type"] == "service"
    assert manifest["homeassistant"] == "2025.2.0"


def test_yaml_setup_registers_nothing(fake_hass):
    hass, registered = fake_hass()
    assert asyncio.run(async_setup(hass, {DOMAIN: {"sources": {}}})) is True
    assert (DOMAIN, "context") not in registered
    assert DOMAIN not in hass.data
    assert any(call[0] == "__flow_init__" for call in hass.config_entries._calls)


def test_async_setup_entry_registers_services(fake_hass):
    from conftest import FakeEntry

    hass, registered = fake_hass()
    asyncio.run(async_setup_entry(hass, FakeEntry(data={})))
    assert (DOMAIN, "context") in registered
    assert (DOMAIN, "generate") in registered
    assert (DOMAIN, "emit") in registered


def test_context_service_returns_context(fake_hass):
    from conftest import FakeEntry, FakeState

    hass, registered = fake_hass(
        {"weather.casa": FakeState("sunny", {"temperature": 21.5})}
    )
    asyncio.run(
        async_setup_entry(
            hass,
            FakeEntry(options={"sources": {"weather": ["weather.casa"]}}),
        )
    )
    handler = registered[(DOMAIN, "context")]
    result = asyncio.run(handler(None))
    assert result["weather"]["weather.casa"]["state"] == "sunny"
    assert "timestamp" in result


def test_generate_service_returns_script(fake_hass, monkeypatch):
    from conftest import FakeEntry

    from custom_components.buenosdias import script

    class FakeLLM:
        async def async_complete(self, system, user):
            return "Good morning, it is sunny today."

    def fake_build(hass, config):
        return FakeLLM()

    monkeypatch.setattr(script, "build_llm", fake_build)

    hass, registered = fake_hass()
    asyncio.run(async_setup_entry(hass, FakeEntry(data={})))
    handler = registered[(DOMAIN, "generate")]
    result = asyncio.run(handler(None))
    assert result["script"] == "Good morning, it is sunny today."