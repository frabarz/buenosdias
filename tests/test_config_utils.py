"""Tests of build_config, which assembles the runtime config from entry data/options."""

import logging

from custom_components.buenosdias.config_schema import BUENOSDIAS_SCHEMA
from custom_components.buenosdias.config_utils import build_config
from custom_components.buenosdias.const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_EXCLUDE,
    CONF_LLM,
    CONF_MODE,
    CONF_MODEL,
    CONF_OPENAI,
    CONF_PERSONA,
    CONF_SCHEDULE,
    CONF_SOURCES,
    CONF_TTS,
    MODE_HA_CONVERSATION,
)


def _openai(data=None, options=None):
    return build_config(
        {"llm": {"openai": data or {}}},
        {"llm": {"openai": options or {}}},
    )["llm"]["openai"]


def test_defaults_are_filled():
    config = build_config({}, {})
    assert config[CONF_LLM][CONF_MODE] == MODE_HA_CONVERSATION
    assert config[CONF_LLM][CONF_OPENAI][CONF_MODEL] == "llama3"
    assert config[CONF_TTS]["language"] == "es-ES"
    assert config[CONF_SCHEDULE]["time"] == "07:00"
    assert config[CONF_PERSONA] == ""
    assert BUENOSDIAS_SCHEMA(config) == config


def test_rss_feed_exclude_is_validated():
    config = build_config(
        {},
        {
            CONF_SOURCES: {
                "rss": {
                    "feeds": [
                        {
                            "url": "https://feeds.example/news",
                            "kind": "news",
                            "exclude": ["futbol", "farándula"],
                        }
                    ]
                }
            }
        },
    )
    feed = config[CONF_SOURCES]["rss"]["feeds"][0]
    assert feed[CONF_EXCLUDE] == ["futbol", "farándula"]


def test_options_sections_are_picked_up():
    config = build_config(
        {},
        {
            CONF_TTS: {"media_player": "media_player.sala"},
            CONF_SOURCES: {"weather": ["weather.casa"]},
            CONF_SCHEDULE: {"time": "08:30"},
            CONF_PERSONA: "Eres un locutor de radio.",
        },
    )
    assert config[CONF_TTS]["media_player"] == "media_player.sala"
    assert config[CONF_SOURCES]["weather"] == ["weather.casa"]
    assert config[CONF_SCHEDULE]["time"] == "08:30"
    assert config[CONF_PERSONA] == "Eres un locutor de radio."


def test_data_survives_empty_options():
    config = build_config(
        {
            CONF_LLM: {
                CONF_MODE: "openai_compatible",
                CONF_OPENAI: {
                    CONF_BASE_URL: "http://x:1234/v1",
                    CONF_MODEL: "my-model",
                    CONF_API_KEY: "secret",
                },
            },
        },
        {},
    )
    openai = config[CONF_LLM][CONF_OPENAI]
    assert openai[CONF_API_KEY] == "secret"
    assert openai[CONF_BASE_URL] == "http://x:1234/v1"
    assert openai[CONF_MODEL] == "my-model"


def test_data_wins_over_options_on_openai_conflict():
    config = build_config(
        {
            CONF_LLM: {
                CONF_OPENAI: {
                    CONF_BASE_URL: "http://data:1/v1",
                    CONF_API_KEY: "secret",
                },
            },
        },
        {CONF_LLM: {CONF_OPENAI: {CONF_BASE_URL: "http://options:2/v1"}}},
    )
    openai = config[CONF_LLM][CONF_OPENAI]
    assert openai[CONF_BASE_URL] == "http://data:1/v1"
    assert openai[CONF_API_KEY] == "secret"


def test_options_fill_openai_fields_missing_in_data():
    openai = _openai(
        data={CONF_BASE_URL: "http://a:1/v1"},
        options={CONF_MODEL: "from-options"},
    )
    assert openai[CONF_BASE_URL] == "http://a:1/v1"
    assert openai[CONF_MODEL] == "from-options"


def test_invalid_options_fall_back_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        config = build_config(
            {},
            {CONF_SCHEDULE: {"time": "not-a-time"}},
        )
    assert any("Invalid buenosdias" in r.message for r in caplog.records)
    assert config[CONF_SCHEDULE]["time"] == "not-a-time"