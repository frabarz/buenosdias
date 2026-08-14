"""Switch platform: enables or disables the good-morning alarm."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> bool:
    """Register the alarm enable switch from a config entry."""
    switch = BuenosdiasEnabledSwitch(hass)
    hass.data[DOMAIN]["entities"].append(switch)
    async_add_entities([switch])
    return True


class BuenosdiasEnabledSwitch(SwitchEntity):
    """Switch that pauses or resumes the daily alarm."""

    _attr_has_entity_name = True
    _attr_name = "enabled"
    _attr_unique_id = "buenosdias_enabled"
    _attr_should_poll = False
    _attr_icon = "mdi:alarm"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._attr_is_on = bool(hass.data[DOMAIN].get("enabled", True))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the alarm."""
        self.hass.data[DOMAIN]["enabled"] = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the alarm."""
        self.hass.data[DOMAIN]["enabled"] = False
        self._attr_is_on = False
        self.async_write_ha_state()
