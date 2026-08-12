"""Plataforma sensor: estado de la última emisión y próxima alarma."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .state import StateStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    """Registra los sensores de estado de la alarma."""
    store: StateStore = hass.data[DOMAIN]["store"]
    sensors = [
        BuenosdiasLastStatusSensor(hass, store),
        BuenosdiasNextAlarmSensor(hass, store),
    ]
    hass.data[DOMAIN]["entities"].extend(sensors)
    async_add_entities(sensors)


class BuenosdiasLastStatusSensor(SensorEntity):
    """Sensor con el resultado de la última emisión."""

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
        """Sincroniza el sensor con el estado persistido."""
        self._attr_native_value = self._store.last_result or "never"
        self._attr_extra_state_attributes = {
            "last_emission_date": self._store.last_emission_date,
            "next_alarm": self._store.next_alarm,
        }


class BuenosdiasNextAlarmSensor(SensorEntity):
    """Sensor con la próxima hora de alarma."""

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
        """Sincroniza el sensor con el estado persistido."""
        self._attr_native_value = self._store.next_alarm or "not_scheduled"
