"""Persistence of the alarm state with homeassistant.helpers.storage.Store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DEFAULT_STORE_KEY = "buenosdias.state"


class StateStore:
    """Stores and retrieves the persistent alarm state.

    Fields:
    - ``last_emission_date``: last date (YYYY-MM-DD) on which it was played.
    - ``last_result``: result of the last playback ("ok" or error description).
    - ``next_alarm``: next alarm time (ISO-8601, UTC) or None.
    - ``last_script``: last generated radio script or None.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store_key: str = DEFAULT_STORE_KEY,
        store: Any | None = None,
    ) -> None:
        self._hass = hass
        self._store = store or Store(hass, 1, store_key)
        self._data: dict[str, str | None] = {
            "last_emission_date": None,
            "last_result": None,
            "next_alarm": None,
            "last_script": None,
        }

    @property
    def last_emission_date(self) -> str | None:
        return self._data["last_emission_date"]

    @property
    def last_result(self) -> str | None:
        return self._data["last_result"]

    @property
    def next_alarm(self) -> str | None:
        return self._data["next_alarm"]

    @property
    def last_script(self) -> str | None:
        return self._data["last_script"]

    async def async_load(self) -> None:
        """Load the persisted state (if any)."""
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            for key in self._data:
                self._data[key] = loaded.get(key) or None

    async def async_set_next_alarm(self, next_alarm: str | None) -> None:
        """Update and persist only the next alarm time."""
        self._data["next_alarm"] = next_alarm
        await self._store.async_save(dict(self._data))

    async def async_set_last_script(self, script_text: str | None) -> None:
        """Update and persist only the last generated script."""
        self._data["last_script"] = script_text
        await self._store.async_save(dict(self._data))

    async def async_mark_emitted(
        self,
        date_str: str,
        result: str = "ok",
        next_alarm: str | None = None,
    ) -> None:
        """Record a playback and persist the state."""
        self._data["last_emission_date"] = date_str
        self._data["last_result"] = result
        self._data["next_alarm"] = next_alarm
        await self._store.async_save(dict(self._data))
