"""Tests de la recolección de contexto desde el estado de HA."""

import asyncio
import json
from types import SimpleNamespace

from custom_components.buenosdias import sources
from custom_components.buenosdias.const import (
    CONF_CALENDAR,
    CONF_SENSORS,
    CONF_SOURCES,
    CONF_WEATHER,
    KIND_EVENTS,
    KIND_NEWS,
)


class FakeState:
    def __init__(self, state, attributes=None, last_updated=None):
        self.state = state
        self.attributes = attributes or {}
        self.last_updated = last_updated


def make_hass(states):
    return SimpleNamespace(states=SimpleNamespace(get=lambda eid: states.get(eid)))


def test_entity_brief_serializable():
    brief = sources.entity_brief(
        "weather.casa",
        FakeState("sunny", {"temperature": 21.5}, last_updated=None),
    )
    assert brief["entity_id"] == "weather.casa"
    assert brief["state"] == "sunny"
    assert brief["attributes"] == {"temperature": 21.5}
    assert brief["last_updated"] is None
    json.dumps(brief)  # debe ser serializable


def test_gather_ha_entities_devuelve_briefs():
    hass = make_hass({"weather.casa": FakeState("sunny", {"temperature": 21.5})})
    result = sources.gather_ha_entities(hass, ["weather.casa"])
    assert result["weather.casa"]["state"] == "sunny"


def test_gather_ha_entities_entidad_inexistente():
    hass = make_hass({})
    result = sources.gather_ha_entities(hass, ["sensor.fantasma"])
    assert result["sensor.fantasma"] == {"error": "entity not found"}


def test_async_gather_context_estructura():
    hass = make_hass(
        {
            "weather.casa": FakeState("rainy", {"temperature": 12.0}),
            "calendar.familia": FakeState("on", {"message": "cita médica 10:00"}),
        }
    )
    config = {
        CONF_SOURCES: {
            CONF_WEATHER: ["weather.casa"],
            CONF_CALENDAR: ["calendar.familia"],
            CONF_SENSORS: [],
        }
    }

    context = asyncio.run(sources.async_gather_context(hass, config))
    assert "timestamp" in context
    assert context[CONF_WEATHER]["weather.casa"]["state"] == "rainy"
    assert context[CONF_CALENDAR]["calendar.familia"]["attributes"]["message"] == "cita médica 10:00"
    assert context[CONF_SENSORS] == {}
    assert context[KIND_NEWS] == []
    assert context[KIND_EVENTS] == []
    json.dumps(context)  # debe ser serializable
