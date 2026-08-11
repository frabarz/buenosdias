"""Persistencia del estado de la alarma con hass.helpers.storage.Store."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

DEFAULT_STORE_KEY = "buenosdias.state"


class StateStore:
    """Almacena y recupera el estado persistente de la alarma.

    Campos:
    - ``last_emission_date``: última fecha (YYYY-MM-DD) en que se emitió.
    - ``last_result``: resultado de la última emisión ("ok" o descripción de error).
    - ``next_alarm``: próxima hora de alarma (ISO-8601, UTC) o None.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store_key: str = DEFAULT_STORE_KEY,
        store: Any | None = None,
    ) -> None:
        self._hass = hass
        self._store = store or hass.helpers.storage.Store(hass, 1, store_key)
        self._data: dict[str, str | None] = {
            "last_emission_date": None,
            "last_result": None,
            "next_alarm": None,
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

    async def async_load(self) -> None:
        """Carga el estado persistido (si existe)."""
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            for key in self._data:
                self._data[key] = loaded.get(key) or None

    async def async_mark_emitted(
        self, date_str: str, result: str = "ok", next_alarm: str | None = None
    ) -> None:
        """Registra una emisión y persiste el estado."""
        self._data["last_emission_date"] = date_str
        self._data["last_result"] = result
        self._data["next_alarm"] = next_alarm
        await self._store.async_save(dict(self._data))
