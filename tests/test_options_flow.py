"""Tests of the buenosdias options flow."""

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.buenosdias.const import (
    CONF_CALENDAR,
    CONF_ENTITY_ID,
    CONF_EXCLUDE,
    CONF_FERIADOS,
    CONF_LLM,
    CONF_MAX_AGE_HOURS,
    CONF_MAX_CHARS,
    CONF_MAX_ITEMS,
    CONF_MEDIA_PLAYER,
    CONF_PERSONA,
    CONF_RSS,
    CONF_SCHEDULE,
    CONF_SENSORS,
    CONF_SOURCES,
    CONF_TAGS,
    CONF_TIME,
    CONF_TTS,
    CONF_URL,
    CONF_WEATHER,
    DOMAIN,
    KIND_EVENTS,
)


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    yield enable_custom_integrations


async def _start_options(hass, entry_id):
    return await hass.config_entries.options.async_init(entry_id)


async def _navigate(hass, flow_id, option):
    return await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": option}
    )


async def _make_entry(hass, data=None, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=data or {},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def test_init_shows_menu(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert set(result["menu_options"]) == {
        "llm",
        "tts",
        "sources",
        "rss_feeds",
        "schedule",
        "persona",
    }


async def test_llm_step_updates_max_chars(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "llm")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"max_chars": 3000}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_LLM][CONF_MAX_CHARS] == 3000
    assert CONF_LLM not in entry.data


async def test_tts_step_updates(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "tts")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "tts.piper",
            CONF_MEDIA_PLAYER: "media_player.sala",
            "language": "es-ES",
            "volume": 0.5,
            "restore_volume": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    tts = entry.options[CONF_TTS]
    assert tts[CONF_ENTITY_ID] == "tts.piper"
    assert tts[CONF_MEDIA_PLAYER] == "media_player.sala"
    assert tts["volume"] == 0.5
    assert tts["restore_volume"] is False


async def test_sources_step_updates_and_keeps_rss(hass):
    entry = await _make_entry(
        hass,
        options={CONF_SOURCES: {CONF_RSS: {"feeds": [{"url": "https://x/rss"}]}}},
    )
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "sources")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_WEATHER: ["weather.casa"],
            CONF_CALENDAR: ["calendar.familia"],
            CONF_SENSORS: [],
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    sources = entry.options[CONF_SOURCES]
    assert sources[CONF_WEATHER] == ["weather.casa"]
    assert sources[CONF_CALENDAR] == ["calendar.familia"]
    assert sources[CONF_SENSORS] == []
    assert sources[CONF_RSS]["feeds"][0]["url"] == "https://x/rss"


async def test_schedule_step_updates(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "schedule")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TIME: "08:30",
            "skip_days": ["sat", "sun"],
            CONF_FERIADOS: "2026-01-01\n2026-05-01",
            "skip_if_emitted": True,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedule = entry.options[CONF_SCHEDULE]
    assert schedule[CONF_TIME] == "08:30"
    assert schedule["skip_days"] == ["sat", "sun"]
    assert schedule[CONF_FERIADOS] == ["2026-01-01", "2026-05-01"]


async def test_schedule_step_rejects_bad_dates(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "schedule")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_TIME: "08:30", CONF_FERIADOS: "not-a-date"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_FERIADOS] == "invalid_date"


async def test_persona_step_updates(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "persona")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PERSONA: "Eres un locutor de radio madrileño."}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PERSONA] == "Eres un locutor de radio madrileño."


async def test_rss_add_appends_feed(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    assert {k for k in result["menu_options"] if isinstance(k, str)} == {"rss_add"}
    result = await _navigate(hass, result["flow_id"], "rss_add")
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rss_add"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://feeds.example/madrid",
            "kind": KIND_EVENTS,
            CONF_MAX_AGE_HOURS: 24,
            CONF_MAX_ITEMS: 3,
            CONF_TAGS: "madrid, cultura",
            CONF_EXCLUDE: "futbol, farandula",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    feeds = entry.options[CONF_SOURCES][CONF_RSS]["feeds"]
    assert feeds[0][CONF_URL] == "https://feeds.example/madrid"
    assert feeds[0]["kind"] == KIND_EVENTS
    assert feeds[0][CONF_MAX_AGE_HOURS] == 24
    assert feeds[0][CONF_MAX_ITEMS] == 3
    assert feeds[0][CONF_TAGS] == ["madrid", "cultura"]
    assert feeds[0][CONF_EXCLUDE] == ["futbol", "farandula"]


async def test_rss_add_rejects_invalid_url(hass):
    entry = await _make_entry(hass)
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "rss_add")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_URL: "not-a-url"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_URL] == "invalid_feed_url"
    assert not entry.options.get(CONF_SOURCES, {}).get(CONF_RSS, {}).get("feeds")


async def _add_feed_via_flow(hass, entry):
    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "rss_add")
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_URL: "https://feeds.example/blogs", CONF_EXCLUDE: "futbol, farandula"},
    )
    return entry


async def test_rss_feeds_menu_lists_feed(hass):
    entry = await _make_entry(hass)
    entry = await _add_feed_via_flow(hass, entry)

    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    assert isinstance(result["menu_options"], dict)
    assert "feed_0" in result["menu_options"]
    assert result["menu_options"]["feed_0"] == "https://feeds.example/blogs"


async def test_rss_edit_updates_feed(hass):
    entry = await _make_entry(hass)
    entry = await _add_feed_via_flow(hass, entry)

    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "feed_0")
    assert result["type"] == FlowResultType.MENU
    result = await _navigate(hass, result["flow_id"], "rss_edit")
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rss_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_URL: "https://feeds.example/edited"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    feeds = entry.options[CONF_SOURCES][CONF_RSS]["feeds"]
    assert len(feeds) == 1
    assert feeds[0][CONF_URL] == "https://feeds.example/edited"


async def test_rss_edit_prefills_exclude(hass):
    entry = await _make_entry(hass)
    entry = await _add_feed_via_flow(hass, entry)

    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "feed_0")
    result = await _navigate(hass, result["flow_id"], "rss_edit")
    assert result["type"] == FlowResultType.FORM
    marker = next(k for k in result["data_schema"].schema if k == CONF_EXCLUDE)
    assert marker.description["suggested_value"] == "futbol, farandula"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_URL: "https://feeds.example/edited", CONF_EXCLUDE: "futbol"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    feeds = entry.options[CONF_SOURCES][CONF_RSS]["feeds"]
    assert feeds[0][CONF_EXCLUDE] == ["futbol"]


async def test_rss_remove_removes_feed(hass):
    entry = await _make_entry(hass)
    entry = await _add_feed_via_flow(hass, entry)

    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "feed_0")
    result = await _navigate(hass, result["flow_id"], "rss_remove")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_remove": True}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SOURCES][CONF_RSS]["feeds"] == []


async def test_rss_remove_unconfirmed_keeps_feed(hass):
    entry = await _make_entry(hass)
    entry = await _add_feed_via_flow(hass, entry)

    result = await _start_options(hass, entry.entry_id)
    result = await _navigate(hass, result["flow_id"], "rss_feeds")
    result = await _navigate(hass, result["flow_id"], "feed_0")
    result = await _navigate(hass, result["flow_id"], "rss_remove")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_remove": False}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "rss_feeds"
    assert len(entry.options[CONF_SOURCES][CONF_RSS]["feeds"]) == 1