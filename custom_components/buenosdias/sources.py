"""Context collection from Home Assistant state and RSS feeds."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from . import rss
from .const import (
    CONF_CALENDAR,
    CONF_FEEDS,
    CONF_RSS,
    CONF_SENSORS,
    CONF_SOURCES,
    CONF_WEATHER,
    KIND_EVENTS,
    KIND_NEWS,
)

_LOGGER = logging.getLogger(__name__)

SECTION_TIMESTAMP = "timestamp"


def entity_brief(entity_id: str, state: Any) -> dict:
    """Return a serializable dict with the essentials of a state."""
    return {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": dict(state.attributes) if state.attributes else {},
        "last_updated": (
            state.last_updated.isoformat(timespec="seconds")
            if state.last_updated
            else None
        ),
    }


def gather_ha_entities(hass: Any, entity_ids: list[str]) -> dict:
    """Return a serializable brief for each requested entity_id."""
    result: dict = {}
    for entity_id in entity_ids or []:
        state = hass.states.get(entity_id)
        if state is None:
            result[entity_id] = {"error": "entity not found"}
            continue
        result[entity_id] = entity_brief(entity_id, state)
    return result


async def async_gather_context(hass: Any, config: dict) -> dict:
    """Collect the morning context (weather, calendar, sensors and RSS)."""
    sources_cfg = config.get(CONF_SOURCES, {})
    feeds = sources_cfg.get(CONF_RSS, {}).get(CONF_FEEDS, [])
    rss_sections = await rss.async_fetch_feeds(hass, feeds)
    return {
        SECTION_TIMESTAMP: datetime.now().isoformat(timespec="seconds"),
        CONF_WEATHER: gather_ha_entities(hass, sources_cfg.get(CONF_WEATHER, [])),
        CONF_CALENDAR: gather_ha_entities(hass, sources_cfg.get(CONF_CALENDAR, [])),
        CONF_SENSORS: gather_ha_entities(hass, sources_cfg.get(CONF_SENSORS, [])),
        KIND_NEWS: rss_sections[KIND_NEWS],
        KIND_EVENTS: rss_sections[KIND_EVENTS],
    }
