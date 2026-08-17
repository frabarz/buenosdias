"""buenosdias integration: personalized morning radio with LLM."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util

from . import coordinator, scheduler, sources
from .config_schema import CONFIG_SCHEMA as CONFIG_SCHEMA
from .config_utils import build_config
from .const import DOMAIN
from .state import StateStore

_LOGGER = logging.getLogger(__name__)

SERVICE_CONTEXT = "context"
SERVICE_GENERATE = "generate"
SERVICE_EMIT = "emit"

PLATFORMS = ("switch", "sensor")


def _is_auth_error(err: Exception) -> bool:
    """Heuristic: does the error look like an API-key/authorization problem?"""
    text = str(err).lower()
    return any(
        token in text
        for token in (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "authentication",
            "invalid api key",
            "invalid token",
        )
    )


def _reauth_entry(data: dict) -> ConfigEntry | None:
    entry = data.get("entry")
    return entry if hasattr(entry, "async_start_reauth") else None


def _async_notify_reauth(hass: HomeAssistant, err: Exception) -> None:
    """Start a reauth flow when the stored API key looks rejected."""
    data = hass.data.get(DOMAIN)
    if data is None or not _is_auth_error(err):
        return
    entry = _reauth_entry(data)
    if entry is None:
        return
    _LOGGER.warning("buenosdias API key was rejected, starting reauthentication")
    entry.async_start_reauth(hass)


async def _async_configure(
    hass: HomeAssistant,
    config: dict,
    entry: ConfigEntry | None = None,
) -> None:
    """Register services, the scheduler and the shared state for a config."""
    store = StateStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = {
        "config": config,
        "enabled": True,
        "store": store,
        "entities": [],
        "entry": entry,
        "unsub_scheduler": None,
    }

    async def async_handle_context(call: ServiceCall) -> dict[str, Any]:
        """Return the collected morning context (JSON)."""
        return await sources.async_gather_context(hass, config)

    async def async_handle_generate(call: ServiceCall) -> dict[str, Any]:
        """Generate the good-morning script (dry-run) and return it."""
        try:
            result = await coordinator.async_run(hass, config, emit=False)
        except coordinator.PipelineError as err:
            _async_notify_reauth(hass, err)
            raise
        return {"script": result["script"]}

    async def async_handle_emit(call: ServiceCall) -> dict[str, Any]:
        """Run the full pipeline and play the script via TTS."""
        try:
            result = await coordinator.async_run(hass, config)
        except coordinator.PipelineError as err:
            _async_notify_reauth(hass, err)
            raise
        return {"script": result["script"]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_CONTEXT,
        async_handle_context,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE,
        async_handle_generate,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EMIT,
        async_handle_emit,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_on_alarm(now) -> None:
        """Fire the daily alarm when it is due."""
        data = hass.data[DOMAIN]
        if not data["enabled"]:
            return
        local_today = dt_util.as_local(now).date()
        holidays = await scheduler.async_holiday_dates(hass, config)
        if not scheduler.should_fire(
            config,
            today=local_today,
            last_emitted_date=store.last_emission_date,
            holiday_dates=holidays,
        ):
            return
        next_alarm = scheduler.next_fire_time(
            config,
            now=now,
            last_emitted_date=store.last_emission_date,
            alarm=scheduler.read_alarm_time(hass, config),
            holiday_dates=holidays,
        )
        try:
            await coordinator.async_run(hass, config)
            result = "ok"
        except coordinator.PipelineError as err:
            _LOGGER.warning("buenosdias alarm failed: %s", err)
            _async_notify_reauth(hass, err)
            result = f"error: {err}"
        await store.async_mark_emitted(
            local_today.isoformat(),
            result,
            next_alarm=next_alarm,
        )
        for entity in data["entities"]:
            refresh = getattr(entity, "refresh_from_store", None)
            if refresh:
                refresh()
            entity.async_write_ha_state()

    data = hass.data[DOMAIN]
    data["unsub_scheduler"] = scheduler.async_setup_scheduler(
        hass,
        config,
        async_on_alarm,
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up from YAML by importing it into a config entry (deprecated path)."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True
    if hass.config_entries.async_has_entries(DOMAIN):
        _LOGGER.warning(
            "buenosdias is already configured through the UI; "
            "remove the YAML block from configuration.yaml",
        )
        return True

    _LOGGER.warning(
        "YAML configuration of buenosdias is deprecated; "
        "migrating to the UI via Settings -> Devices & Services",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=conf,
        ),
        "config entry import buenosdias",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up buenosdias from a config entry."""
    config = build_config(entry.data, entry.options)
    await _async_configure(hass, config, entry=entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.data[DOMAIN]["unsub_update_listener"] = entry.add_update_listener(
        _async_update_listener,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload buenosdias."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN)
    if data is not None:
        unsub = data.get("unsub_scheduler")
        if unsub is not None:
            unsub()
        unsub_listener = data.get("unsub_update_listener")
        if unsub_listener is not None:
            unsub_listener()
        for service in (SERVICE_CONTEXT, SERVICE_GENERATE, SERVICE_EMIT):
            hass.services.async_remove(DOMAIN, service)
        hass.data.pop(DOMAIN, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry to a new version."""
    return True
