"""Tests of the buenosdias config flow (user, reconfigure, reauth)."""

import httpx
import pytest
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
)
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.buenosdias import config_flow as flow
from custom_components.buenosdias.const import (
    CONF_AGENT,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_LLM,
    CONF_MODE,
    CONF_MODEL,
    CONF_OPENAI,
    DOMAIN,
    MODE_HA_CONVERSATION,
    MODE_OPENAI_COMPATIBLE,
)


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    yield enable_custom_integrations


LEGACY_ENTRY_DATA = {
    CONF_LLM: {
        CONF_MODE: MODE_OPENAI_COMPATIBLE,
        CONF_OPENAI: {
            CONF_BASE_URL: "https://llm.example/v1",
            CONF_MODEL: "llama3",
            CONF_API_KEY: "old-secret",
        },
    },
}


async def test_user_flow_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_HA_CONVERSATION},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_agent"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Buenos Días"
    assert result["data"][CONF_LLM][CONF_MODE] == MODE_HA_CONVERSATION


async def test_user_flow_ha_mode_with_agent(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_HA_CONVERSATION},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_agent"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AGENT: "conversation.local"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LLM][CONF_AGENT] == "conversation.local"


async def test_user_flow_openai_requires_base_url(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_openai"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_BASE_URL] == "missing_base_url"


async def test_user_flow_openai_invalid_url(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "not a url"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_BASE_URL] == "invalid_url"


async def test_user_flow_openai_creates_entry(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_openai"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://llm.example/v1",
            CONF_MODEL: "qwen2.5",
            CONF_API_KEY: "s3cr3t",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    openai = result["data"][CONF_LLM][CONF_OPENAI]
    assert openai[CONF_BASE_URL] == "https://llm.example/v1"
    assert openai[CONF_MODEL] == "qwen2.5"
    assert openai[CONF_API_KEY] == "s3cr3t"


async def test_user_flow_openai_connection_error(hass, monkeypatch):
    async def fake_error(*args, **kwargs):
        return "invalid_auth"

    monkeypatch.setattr(flow, "_async_validate_connection", fake_error)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://llm.example/v1",
            CONF_API_KEY: "wrong",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_import_flow_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_LLM: {
                CONF_MODE: MODE_OPENAI_COMPATIBLE,
                CONF_OPENAI: {
                    CONF_BASE_URL: "https://yaml.example/v1",
                    CONF_MODEL: "llama3",
                    CONF_API_KEY: "yaml-secret",
                },
            },
            "tts": {"media_player": "media_player.sala"},
            "sources": {"weather": ["weather.casa"]},
            "schedule": {"time": "07:00"},
            "persona": "Eres un locutor de radio.",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = result["result"]
    llm = entry.data[CONF_LLM]
    assert llm[CONF_MODE] == MODE_OPENAI_COMPATIBLE
    assert llm[CONF_OPENAI][CONF_API_KEY] == "yaml-secret"
    assert llm[CONF_OPENAI][CONF_BASE_URL] == "https://yaml.example/v1"
    assert entry.options["tts"]["media_player"] == "media_player.sala"
    assert entry.options["sources"]["weather"] == ["weather.casa"]
    assert entry.options["schedule"]["time"] == "07:00"
    assert entry.options["persona"] == "Eres un locutor de radio."


async def test_import_flow_moves_max_chars_to_options(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LLM: {CONF_MODE: MODE_HA_CONVERSATION, "max_chars": 1500}},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data[CONF_LLM] == {CONF_MODE: MODE_HA_CONVERSATION}
    assert entry.options[CONF_LLM] == {"max_chars": 1500}


async def test_single_config_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODE: MODE_HA_CONVERSATION}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    entry = next(
        e for e in hass.config_entries.async_entries(DOMAIN) if e.domain == DOMAIN
    )
    assert isinstance(entry, ConfigEntry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_updates_entry(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=LEGACY_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_openai"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://new.example/v1",
            CONF_MODEL: "llama3.1",
            CONF_API_KEY: "new-secret",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    openai = entry.data[CONF_LLM][CONF_OPENAI]
    assert openai[CONF_BASE_URL] == "https://new.example/v1"
    assert openai[CONF_MODEL] == "llama3.1"
    assert openai[CONF_API_KEY] == "new-secret"


async def test_reconfigure_switches_openai_to_ha_conversation(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=LEGACY_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_HA_CONVERSATION},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_agent"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    llm = entry.data[CONF_LLM]
    assert llm[CONF_MODE] == MODE_HA_CONVERSATION
    assert CONF_OPENAI not in llm
    assert CONF_AGENT not in llm


async def test_reconfigure_switches_ha_conversation_to_openai(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_LLM: {CONF_MODE: MODE_HA_CONVERSATION}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_openai"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://switched.example/v1",
            CONF_MODEL: "gpt-4o-mini",
            CONF_API_KEY: "switched-secret",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    llm = entry.data[CONF_LLM]
    assert llm[CONF_MODE] == MODE_OPENAI_COMPATIBLE
    assert llm[CONF_OPENAI][CONF_BASE_URL] == "https://switched.example/v1"
    assert llm[CONF_OPENAI][CONF_MODEL] == "gpt-4o-mini"
    assert llm[CONF_OPENAI][CONF_API_KEY] == "switched-secret"


async def test_reconfigure_openai_keeps_api_key_when_empty(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=LEGACY_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODE: MODE_OPENAI_COMPATIBLE},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://new.example/v1",
            CONF_MODEL: "llama3.1",
            CONF_API_KEY: "",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    openai = entry.data[CONF_LLM][CONF_OPENAI]
    assert openai[CONF_BASE_URL] == "https://new.example/v1"
    assert openai[CONF_MODEL] == "llama3.1"
    assert openai[CONF_API_KEY] == "old-secret"


async def test_reauth_updates_api_key(hass, monkeypatch):
    async def no_error(*args, **kwargs):
        return None

    monkeypatch.setattr(flow, "_async_validate_connection", no_error)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=LEGACY_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "fresh-key"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_LLM][CONF_OPENAI][CONF_API_KEY] == "fresh-key"


class _FakeResponse:
    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("GET", "https://x"), response=self
            )


class _FakeClient:
    def __init__(self, status):
        self.status = status

    async def get(self, url, headers=None, timeout=None):
        return _FakeResponse(self.status)


async def test_validate_connection_ok(hass, monkeypatch):
    monkeypatch.setattr(
        flow.httpx_client, "get_async_client", lambda hass, verify_ssl=True: _FakeClient(200)
    )
    assert await flow._async_validate_connection(hass, "https://x/v1", None) is None


async def test_validate_connection_invalid_auth(hass, monkeypatch):
    monkeypatch.setattr(
        flow.httpx_client, "get_async_client", lambda hass, verify_ssl=True: _FakeClient(401)
    )
    assert (
        await flow._async_validate_connection(hass, "https://x/v1", "bad")
        == "invalid_auth"
    )


async def test_validate_connection_server_error(hass, monkeypatch):
    monkeypatch.setattr(
        flow.httpx_client, "get_async_client", lambda hass, verify_ssl=True: _FakeClient(500)
    )
    assert (
        await flow._async_validate_connection(hass, "https://x/v1", None)
        == "cannot_connect"
    )
