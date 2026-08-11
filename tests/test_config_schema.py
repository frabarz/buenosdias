"""Tests del esquema de configuración de buenosdias."""

import pytest
import voluptuous as vol

from custom_components.buenosdias.config_schema import CONFIG_SCHEMA
from custom_components.buenosdias.const import (
    CONF_LLM,
    CONF_MODE,
    CONF_RSS,
    CONF_SCHEDULE,
    CONF_SOURCES,
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TTS,
    CONF_URL,
    DOMAIN,
    KIND_EVENTS,
    MODE_HA_CONVERSATION,
)


def test_schema_acepta_configuracion_completa():
    config = {
        DOMAIN: {
            "llm": {"mode": "openai_compatible", "max_chars": 1500},
            "tts": {"entity_id": "tts.piper", "media_player": "media_player.sala"},
            "sources": {"weather": ["weather.casa"], "sensors": ["sensor.x"]},
            "schedule": {"time": "06:30", "skip_days": ["sat", "sun"]},
            "persona": "Eres un locutor de radio.",
        }
    }
    validated = CONFIG_SCHEMA(config)
    assert validated[DOMAIN]["llm"][CONF_MODE] == "openai_compatible"
    assert validated[DOMAIN]["schedule"]["time"] == "06:30"


def test_schema_aplica_defaults():
    validated = CONFIG_SCHEMA({DOMAIN: {}})
    conf = validated[DOMAIN]
    assert conf[CONF_LLM][CONF_MODE] == MODE_HA_CONVERSATION
    assert conf[CONF_LLM]["max_chars"] == 2000
    assert conf[CONF_TTS]["language"] == "es-ES"
    assert conf[CONF_TTS]["volume"] == 0.6
    assert conf[CONF_SOURCES]["weather"] == []
    assert conf[CONF_SCHEDULE][CONF_TIME] == "07:00"


def test_schema_acepta_time_entity():
    config = {
        DOMAIN: {"schedule": {CONF_TIME_ENTITY: "sensor.alarma_telefono"}}
    }
    validated = CONFIG_SCHEMA(config)
    assert (
        validated[DOMAIN][CONF_SCHEDULE][CONF_TIME_ENTITY]
        == "sensor.alarma_telefono"
    )


def test_schema_aplica_default_time_entity():
    validated = CONFIG_SCHEMA({DOMAIN: {}})
    assert validated[DOMAIN][CONF_SCHEDULE][CONF_TIME_ENTITY] == ""


def test_schema_permite_ausencia_de_la_seccion():
    validated = CONFIG_SCHEMA({"otra_integracion": {}})
    assert DOMAIN not in validated


def test_schema_permite_claves_extra_top_level():
    validated = CONFIG_SCHEMA({DOMAIN: {}, "otra_integracion": {"a": 1}})
    assert DOMAIN in validated


def test_schema_acepta_feeds_rss():
    config = {
        DOMAIN: {
            "sources": {
                "rss": {
                    "feeds": [
                        {
                            CONF_URL: "https://ejemplo.org/noticias.xml",
                            "kind": "news",
                            "max_age_hours": 24,
                            "max_items": 5,
                            "tags": ["ciudad"],
                        },
                        {
                            CONF_URL: "https://ejemplo.org/agenda.xml",
                            "kind": "events",
                        },
                    ]
                }
            }
        }
    }
    validated = CONFIG_SCHEMA(config)
    feeds = validated[DOMAIN][CONF_SOURCES][CONF_RSS]["feeds"]
    assert feeds[0]["kind"] == "news"
    assert feeds[0]["tags"] == ["ciudad"]
    assert feeds[1]["kind"] == KIND_EVENTS
    assert feeds[1]["max_items"] == 5  # default aplicado


def test_schema_aplica_defaults_rss():
    validated = CONFIG_SCHEMA({DOMAIN: {}})
    assert validated[DOMAIN][CONF_SOURCES][CONF_RSS]["feeds"] == []


@pytest.mark.parametrize(
    "bad_config",
    [
        {DOMAIN: {"schedule": {"time": "25:00"}}},
        {DOMAIN: {"schedule": {"skip_days": ["lunes"]}}},
        {DOMAIN: {"schedule": {"feriados": ["01-01-2026"]}}},
        {DOMAIN: {"tts": {"volume": 1.5}}},
        {DOMAIN: {"llm": {"mode": "no_existe"}}},
        {DOMAIN: {"llm": {"max_chars": 5}}},
        {DOMAIN: {"sources": {"rss": {"feeds": [{"url": ""}]}}}},
        {DOMAIN: {"sources": {"rss": {"feeds": [{"url": "https://x.es", "kind": "deportes"}]}}}},
        {DOMAIN: {"sources": {"rss": {"feeds": [{"url": "https://x.es", "max_age_hours": 0}]}}}},
    ],
)
def test_schema_rechaza_configuracion_invalida(bad_config):
    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(bad_config)
