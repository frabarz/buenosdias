"""Switch platform: enables or disables the good-morning alarm."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, VERSION

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _device_info(entry: Any) -> DeviceInfo:
    """Device info shared by the buenosdias entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Buenos Días",
        manufacturer="Buenos Días",
        model="Morning radio",
        sw_version=VERSION,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> bool:
    """Register the alarm enable switch from a config entry."""
    switch = BuenosdiasEnabledSwitch(hass, entry)
    hass.data[DOMAIN]["entities"].append(switch)
    async_add_entities([switch])
    return True


class BuenosdiasEnabledSwitch(SwitchEntity):
    """Switch that pauses or resumes the daily alarm."""

    _attr_has_entity_name = True
    _attr_translation_key = "enabled"
    _attr_unique_id = "buenosdias_enabled"
    _attr_should_poll = False
    _attr_icon = "mdi:alarm"

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self._attr_device_info = _device_info(entry)
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
