"""Tests of the entry lifecycle: async_setup_entry, async_unload_entry, YAML shim."""

import asyncio

from custom_components.buenosdias import (
    DOMAIN,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.buenosdias.const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_LLM,
    CONF_MODE,
    CONF_OPENAI,
    CONF_TTS,
    MODE_OPENAI_COMPATIBLE,
)

ENTRY_DATA = {
    CONF_LLM: {
        CONF_MODE: MODE_OPENAI_COMPATIBLE,
        CONF_OPENAI: {
            CONF_BASE_URL: "https://llm.example/v1",
            CONF_API_KEY: "s3cret-key",
        },
    },
}


def test_async_setup_entry_assembles_config(fake_hass):
    from conftest import FakeEntry

    hass, registered = fake_hass()
    entry = FakeEntry(
        data=ENTRY_DATA,
        options={CONF_TTS: {"media_player": "media_player.sala"}},
    )
    asyncio.run(async_setup_entry(hass, entry))

    assert (DOMAIN, "context") in registered
    assert (DOMAIN, "generate") in registered
    assert (DOMAIN, "emit") in registered

    data = hass.data[DOMAIN]
    assert data["entry"] is entry
    assert data["config"][CONF_LLM][CONF_OPENAI][CONF_API_KEY] == "s3cret-key"
    assert data["config"][CONF_LLM][CONF_OPENAI][CONF_BASE_URL] == "https://llm.example/v1"
    assert data["config"][CONF_TTS]["media_player"] == "media_player.sala"

    assert ("__forward__", entry.entry_id, ["switch", "sensor"]) in hass.calls
    assert entry.listeners


def test_async_setup_entry_llm_mode_from_data(fake_hass):
    from conftest import FakeEntry

    hass, _ = fake_hass()
    entry = FakeEntry(data=ENTRY_DATA, options={})
    asyncio.run(async_setup_entry(hass, entry))
    assert (
        hass.data[DOMAIN]["config"][CONF_LLM][CONF_MODE] == MODE_OPENAI_COMPATIBLE
    )


def test_async_unload_entry_tears_down(fake_hass):
    from conftest import FakeEntry

    hass, registered = fake_hass()
    entry = FakeEntry(data=ENTRY_DATA)
    asyncio.run(async_setup_entry(hass, entry))
    assert DOMAIN in hass.data

    assert asyncio.run(async_unload_entry(hass, entry)) is True
    assert ("__unload__", entry.entry_id, ["switch", "sensor"]) in hass.calls
    assert DOMAIN not in hass.data
    assert (DOMAIN, "context") not in registered
    assert (DOMAIN, "generate") not in registered
    assert (DOMAIN, "emit") not in registered


def test_yaml_setup_triggers_import_when_no_entry(fake_hass):
    hass, registered = fake_hass()
    assert asyncio.run(async_setup(hass, {DOMAIN: {"sources": {}}})) is True
    assert (DOMAIN, "context") not in registered
    assert DOMAIN not in hass.data
    assert any(call[0] == "__flow_init__" for call in hass.config_entries._calls)


def test_yaml_setup_without_block_returns_true(fake_hass):
    hass, registered = fake_hass()
    assert asyncio.run(async_setup(hass, {})) is True
    assert (DOMAIN, "context") not in registered
    assert not any(call[0] == "__flow_init__" for call in hass.config_entries._calls)


def test_yaml_setup_skipped_when_entry_exists(fake_hass):
    from conftest import FakeEntry

    hass, registered = fake_hass()
    hass.config_entries.entries.append(FakeEntry(data={}))
    assert asyncio.run(async_setup(hass, {DOMAIN: {"sources": {}}})) is True
    assert (DOMAIN, "context") not in registered
    assert DOMAIN not in hass.data
    assert not any(call[0] == "__flow_init__" for call in hass.config_entries._calls)


def _run_alarm(fake_hass, fake_trackers, monkeypatch, message):
    from datetime import UTC, datetime

    from conftest import FakeEntry

    from custom_components.buenosdias import coordinator

    async def boom(hass, config, emit=True):
        raise coordinator.PipelineError(message)

    monkeypatch.setattr(coordinator, "async_run", boom)
    hass, _ = fake_hass()
    entry = FakeEntry(data={})
    asyncio.run(async_setup_entry(hass, entry))
    callback = fake_trackers.track_calls[0]["callback"]
    asyncio.run(callback(datetime(2026, 8, 10, 7, 0, tzinfo=UTC)))
    return entry


def test_alarm_auth_error_triggers_reauth(fake_hass, fake_trackers, monkeypatch):
    entry = _run_alarm(
        fake_hass, fake_trackers, monkeypatch, "OpenAI endpoint failed: 401 Unauthorized"
    )
    assert entry.reauth_started


def test_alarm_other_error_does_not_trigger_reauth(
    fake_hass, fake_trackers, monkeypatch
):
    entry = _run_alarm(fake_hass, fake_trackers, monkeypatch, "network is down")
    assert not entry.reauth_started