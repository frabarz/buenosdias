"""Daily alarm scheduling and skip logic."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers import event as ha_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FERIADOS,
    CONF_SCHEDULE,
    CONF_SKIP_DAYS,
    CONF_SKIP_IF_EMITTED,
    CONF_TIME,
    CONF_TIME_ENTITY,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIME = "07:00"
MAX_LOOKAHEAD_DAYS = 60

_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$")

WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_time(value: str | datetime) -> tuple[int, int]:
    """Normalize 'HH:MM', 'HH:MM:SS' or ISO datetime into (hour, minute)."""
    if isinstance(value, datetime):
        return value.hour, value.minute

    value = str(value).strip()
    if _TIME_RE.match(value):
        hour, minute = (int(part) for part in value.split(":")[:2])
    else:
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            msg = f"Invalid alarm time: {value!r}"
            raise ValueError(msg)
        if parsed.tzinfo is not None:
            parsed = dt_util.as_local(parsed)
        hour, minute = parsed.hour, parsed.minute
    return hour, minute


def read_alarm_time(hass: HomeAssistant, config: dict) -> tuple[int, int] | None:
    """Return (hour, minute) from time_entity or the static time.

    Returns None if time_entity is not available or its value cannot be parsed.
    """
    schedule = config.get(CONF_SCHEDULE, {})
    time_entity = schedule.get(CONF_TIME_ENTITY, "")
    if time_entity:
        state = hass.states.get(time_entity)
        if state is None or state.state in ("", "unavailable", "unknown", "none"):
            _LOGGER.warning(
                "time_entity %s not available; alarm disabled",
                time_entity,
            )
            return None
        try:
            return parse_time(state.state)
        except ValueError as err:
            _LOGGER.warning("time_entity %s has an invalid time: %s", time_entity, err)
            return None
    return parse_time(schedule.get(CONF_TIME, DEFAULT_TIME))


def _day_allowed(day: date, schedule: dict) -> bool:
    """Return whether the day is not skipped by skip_days or feriados."""
    skip_days = schedule.get(CONF_SKIP_DAYS, [])
    if day.weekday() in {WEEKDAY_MAP[name] for name in skip_days}:
        return False

    feriados = schedule.get(CONF_FERIADOS, [])
    return day.isoformat() not in feriados


def should_fire(
    config: dict,
    today: date | None = None,
    last_emitted_date: str | None = None,
) -> bool:
    """Decide whether the alarm should fire today based on the configuration."""
    schedule = config.get(CONF_SCHEDULE, {})
    today = today or dt_util.as_local(dt_util.utcnow()).date()

    if not _day_allowed(today, schedule):
        return False

    return not (
        schedule.get(CONF_SKIP_IF_EMITTED, True)
        and last_emitted_date == today.isoformat()
    )


def next_fire_time(
    config: dict,
    now: datetime | None = None,
    last_emitted_date: str | None = None,
    max_days: int = MAX_LOOKAHEAD_DAYS,
    alarm: tuple[int, int] | None = None,
) -> str | None:
    """Compute the next alarm time (ISO-8601 UTC) or None."""
    schedule = config.get(CONF_SCHEDULE, {})
    local_now = dt_util.as_local(now or dt_util.utcnow())
    now_utc = dt_util.as_utc(now or dt_util.utcnow())
    hour, minute = alarm or parse_time(schedule.get(CONF_TIME, DEFAULT_TIME))
    skip_if_emitted = schedule.get(CONF_SKIP_IF_EMITTED, True)
    today = local_now.date()

    for offset in range(max_days):
        day = today + timedelta(days=offset)
        if not _day_allowed(day, schedule):
            continue
        if offset == 0 and skip_if_emitted and last_emitted_date == day.isoformat():
            continue
        local_fire = datetime.combine(day, time(hour, minute), tzinfo=local_now.tzinfo)
        fire_utc = dt_util.as_utc(local_fire)
        if fire_utc <= now_utc:
            continue
        return fire_utc.isoformat()

    return None


def async_setup_scheduler(
    hass: HomeAssistant,
    config: dict,
    callback: Callable,
) -> Callable[[], None]:
    """Register the daily trigger; with time_entity it re-registers on state change.

    Returns the cancellation function for the scheduler and the state listener.
    """
    schedule = config.get(CONF_SCHEDULE, {})
    time_entity = schedule.get(CONF_TIME_ENTITY, "")

    def _arm() -> Callable[[], None] | None:
        alarm = read_alarm_time(hass, config)
        if alarm is None:
            return None
        hour, minute = alarm
        return ha_event.async_track_utc_time_change(
            hass,
            callback,
            hour=hour,
            minute=minute,
            second=0,
        )

    unsub_time = _arm()
    unsub_state = None

    if time_entity:

        async def async_on_state_change(event) -> None:
            nonlocal unsub_time
            if unsub_time is not None:
                unsub_time()
            unsub_time = _arm()

        unsub_state = ha_event.async_track_state_change_event(
            hass,
            [time_entity],
            async_on_state_change,
        )

    def async_unsub() -> None:
        if unsub_time is not None:
            unsub_time()
        if unsub_state is not None:
            unsub_state()

    return async_unsub
