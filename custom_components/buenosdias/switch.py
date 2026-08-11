"""Plataforma switch: habilita o deshabilita la alarma del buenos días."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    """Registra el switch de habilitación de la alarma."""
    switch = BuenosdiasEnabledSwitch(hass)
    hass.data[DOMAIN]["entities"].append(switch)
    async_add_entities([switch])


class BuenosdiasEnabledSwitch(SwitchEntity):
    """Switch que pausa o reanuda la alarma diaria."""

    _attr_has_entity_name = True
    _attr_name = "enabled"
    _attr_unique_id = "buenosdias_enabled"
    _attr_should_poll = False
    _attr_icon = "mdi:alarm"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._attr_is_on = bool(hass.data[DOMAIN].get("enabled", True))

    async def async_turn_on(self, **kwargs) -> None:
        """Habilita la alarma."""
        self.hass.data[DOMAIN]["enabled"] = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Deshabilita la alarma."""
        self.hass.data[DOMAIN]["enabled"] = False
        self._attr_is_on = False
        self.async_write_ha_state()
