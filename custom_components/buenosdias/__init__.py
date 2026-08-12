"""buenosdias integration: personalized morning radio with LLM."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import discovery
from homeassistant.util import dt as dt_util

from . import coordinator, scheduler, sources
from .config_schema import CONFIG_SCHEMA  # noqa: F401  (exposed to HA)
from .const import DOMAIN
from .state import StateStore

_LOGGER = logging.getLogger(__name__)

SERVICE_CONTEXT = "context"
SERVICE_GENERATE = "generate"
SERVICE_EMIT = "emit"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the buenosdias integration."""
    conf = config.get(DOMAIN, {})
    store = StateStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = {
        "config": conf,
        "enabled": True,
        "store": store,
        "entities": [],
    }

    async def async_handle_context(call: ServiceCall) -> dict[str, Any]:
        """Return the collected morning context (JSON)."""
        return await sources.async_gather_context(hass, conf)

    async def async_handle_generate(call: ServiceCall) -> dict[str, Any]:
        """Generate the good-morning script (dry-run) and return it."""
        result = await coordinator.async_run(hass, conf, emit=False)
        return {"script": result["script"]}

    async def async_handle_emit(call: ServiceCall) -> dict[str, Any]:
        """Run the full pipeline and play the script via TTS."""
        result = await coordinator.async_run(hass, conf)
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
        entry = hass.data[DOMAIN]
        if not entry["enabled"]:
            return
        local_today = dt_util.as_local(now).date()
        if not scheduler.should_fire(
            conf,
            today=local_today,
            last_emitted_date=store.last_emission_date,
        ):
            return
        next_alarm = scheduler.next_fire_time(
            conf,
            now=now,
            last_emitted_date=store.last_emission_date,
            alarm=scheduler.read_alarm_time(hass, conf),
        )
        try:
            await coordinator.async_run(hass, conf)
            result = "ok"
        except coordinator.PipelineError as err:
            _LOGGER.warning("buenosdias alarm failed: %s", err)
            result = f"error: {err}"
        await store.async_mark_emitted(
            local_today.isoformat(),
            result,
            next_alarm=next_alarm,
        )
        for entity in entry["entities"]:
            refresh = getattr(entity, "refresh_from_store", None)
            if refresh:
                refresh()
            entity.async_write_ha_state()

    scheduler.async_setup_scheduler(hass, conf, async_on_alarm)

    for platform in ("switch", "sensor"):
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config),
            f"buenosdias setup {platform} platform",
        )

    return True
