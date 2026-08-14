"""Sensor platform: last playback status and next alarm."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .state import StateStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> bool:
    """Register the alarm status sensors from a config entry."""
    store: StateStore = hass.data[DOMAIN]["store"]
    sensors = [
        BuenosdiasLastStatusSensor(hass, store),
        BuenosdiasNextAlarmSensor(hass, store),
    ]
    hass.data[DOMAIN]["entities"].extend(sensors)
    async_add_entities(sensors)
    return True


class BuenosdiasLastStatusSensor(SensorEntity):
    """Sensor with the result of the last playback."""

    _attr_has_entity_name = True
    _attr_name = "last_status"
    _attr_unique_id = "buenosdias_last_status"
    _attr_should_poll = False
    _attr_icon = "mdi:calendar-check"

    def __init__(self, hass: HomeAssistant, store: StateStore) -> None:
        self.hass = hass
        self._store = store
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """Sync the sensor with the persisted state."""
        self._attr_native_value = self._store.last_result or "never"
        self._attr_extra_state_attributes = {
            "last_emission_date": self._store.last_emission_date,
            "next_alarm": self._store.next_alarm,
        }


class BuenosdiasNextAlarmSensor(SensorEntity):
    """Sensor with the next alarm time."""

    _attr_has_entity_name = True
    _attr_name = "next_alarm"
    _attr_unique_id = "buenosdias_next_alarm"
    _attr_should_poll = False
    _attr_icon = "mdi:alarm"

    def __init__(self, hass: HomeAssistant, store: StateStore) -> None:
        self.hass = hass
        self._store = store
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """Sync the sensor with the persisted state."""
        self._attr_native_value = self._store.next_alarm or "not_scheduled"
