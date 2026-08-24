"""Daily alarm scheduling and skip logic."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.calendar.const import DATA_COMPONENT as CALENDAR_COMPONENT
from homeassistant.helpers import event as ha_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FERIADOS,
    CONF_HOLIDAY_CALENDAR,
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


def _day_allowed(
    day: date, schedule: dict, holiday_dates: set[str] | None = None,
) -> bool:
    """Return whether the day is not skipped by skip_days or holidays."""
    skip_days = schedule.get(CONF_SKIP_DAYS, [])
    if day.weekday() in {WEEKDAY_MAP[name] for name in skip_days}:
        return False

    feriados = set(schedule.get(CONF_FERIADOS, []))
    if holiday_dates:
        feriados.update(holiday_dates)
    return day.isoformat() not in feriados


async def async_holiday_dates(
    hass: HomeAssistant,
    config: dict,
    days: int = MAX_LOOKAHEAD_DAYS,
) -> set[str]:
    """Resolve the ISO dates (YYYY-MM-DD) on which the alarm is skipped.

    Always includes the manually configured ``feriados``. When the schedule
    points to a holiday calendar (e.g. from the Home Assistant Holiday
    integration), the calendar is asked for every event within the next
    ``days`` days and those dates are added.
    """
    schedule = config.get(CONF_SCHEDULE, {})
    dates = set(schedule.get(CONF_FERIADOS, []))
    calendar_entity = schedule.get(CONF_HOLIDAY_CALENDAR, "")
    if not calendar_entity:
        return dates

    component = hass.data.get(CALENDAR_COMPONENT)
    entity = component.get_entity(calendar_entity) if component else None
    if entity is None or not hasattr(entity, "async_get_events"):
        _LOGGER.warning(
            "holiday_calendar %s not available; falling back to the manual holidays",
            calendar_entity,
        )
        return dates

    now = dt_util.now()
    start = dt_util.start_of_local_day(now)
    end = start + timedelta(days=days)
    try:
        events = await entity.async_get_events(hass, start, end)
    except Exception:
        _LOGGER.exception("could not read holidays from %s", calendar_entity)
        return dates

    for event in events:
        event_start = event.start
        if isinstance(event_start, datetime):
            event_start = dt_util.as_local(event_start).date()
        dates.add(event_start.isoformat())
    return dates


def should_fire(
    config: dict,
    today: date | None = None,
    last_emitted_date: str | None = None,
    holiday_dates: set[str] | None = None,
) -> bool:
    """Decide whether the alarm should fire today based on the configuration."""
    schedule = config.get(CONF_SCHEDULE, {})
    today = today or dt_util.as_local(dt_util.utcnow()).date()

    if not _day_allowed(today, schedule, holiday_dates):
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
    holiday_dates: set[str] | None = None,
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
        if not _day_allowed(day, schedule, holiday_dates):
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
    on_rearm: Callable[[], Any] | None = None,
) -> Callable[[], None]:
    """Register the daily trigger; with time_entity it re-registers on state change.

    ``on_rearm`` (if given, a coroutine function) is scheduled as a task after
    each re-registration triggered by a time_entity state change. Returns the
    cancellation function for the scheduler and the state listener.
    """
    schedule = config.get(CONF_SCHEDULE, {})
    time_entity = schedule.get(CONF_TIME_ENTITY, "")

    def _arm() -> Callable[[], None] | None:
        alarm = read_alarm_time(hass, config)
        if alarm is None:
            return None
        hour, minute = alarm
        return ha_event.async_track_time_change(
            hass,
            callback,
            hour=hour,
            minute=minute,
            second=0,
        )

    unsub_time = _arm()
    unsub_state = None

    if time_entity:

        def _on_state_change(event) -> None:
            nonlocal unsub_time
            if unsub_time is not None:
                unsub_time()
            unsub_time = _arm()
            if on_rearm is not None:
                hass.async_create_task(on_rearm())

        unsub_state = ha_event.async_track_state_change_event(
            hass,
            [time_entity],
            _on_state_change,
        )

    def async_unsub() -> None:
        if unsub_time is not None:
            unsub_time()
        if unsub_state is not None:
            unsub_state()

    return async_unsub
