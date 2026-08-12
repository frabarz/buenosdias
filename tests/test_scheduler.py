"""Tests of the daily scheduling and skip logic."""

import asyncio
from datetime import date, datetime, timezone

from custom_components.buenosdias import async_setup
from custom_components.buenosdias.const import CONF_TIME_ENTITY, DOMAIN
from custom_components.buenosdias import scheduler
from custom_components.buenosdias.scheduler import (
    next_fire_time,
    parse_time,
    read_alarm_time,
    should_fire,
)

CONF_SCHEDULE = "schedule"
CONF_SKIP_DAYS = "skip_days"
CONF_FERIADOS = "feriados"
CONF_SKIP_IF_EMITTED = "skip_if_emitted"
CONF_TIME = "time"


def _now():
    return datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)  # monday


def test_should_fire_default_true():
    assert should_fire({}) is True


def test_should_fire_skips_by_day():
    config = {CONF_SCHEDULE: {CONF_SKIP_DAYS: ["sat", "sun"]}}
    saturday = date(2026, 8, 15)
    monday = date(2026, 8, 17)
    assert should_fire(config, today=saturday) is False
    assert should_fire(config, today=monday) is True


def test_should_fire_skips_holiday():
    config = {CONF_SCHEDULE: {CONF_FERIADOS: ["2026-08-10"]}}
    assert should_fire(config, today=date(2026, 8, 10)) is False
    assert should_fire(config, today=date(2026, 8, 11)) is True


def test_should_fire_skip_if_emitted():
    config = {CONF_SCHEDULE: {CONF_SKIP_IF_EMITTED: True}}
    today = date(2026, 8, 10)
    assert should_fire(config, today=today, last_emitted_date="2026-08-10") is False
    assert should_fire(config, today=today, last_emitted_date="2026-08-09") is True


def test_should_fire_skip_if_emitted_disabled():
    config = {CONF_SCHEDULE: {CONF_SKIP_IF_EMITTED: False}}
    today = date(2026, 8, 10)
    assert should_fire(config, today=today, last_emitted_date="2026-08-10") is True


def test_next_fire_time_today_if_not_passed():
    result = next_fire_time({CONF_SCHEDULE: {CONF_TIME: "07:00"}}, now=_now())
    assert result == "2026-08-10T07:00:00+00:00"


def test_next_fire_time_tomorrow_if_passed():
    now = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    result = next_fire_time({CONF_SCHEDULE: {CONF_TIME: "07:00"}}, now=now)
    assert result == "2026-08-11T07:00:00+00:00"


def test_next_fire_time_skips_weekend():
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)  # friday
    config = {CONF_SCHEDULE: {CONF_TIME: "07:00", CONF_SKIP_DAYS: ["sat", "sun"]}}
    result = next_fire_time(config, now=now)
    assert result == "2026-08-17T07:00:00+00:00"


def test_next_fire_time_skips_holiday_tomorrow():
    now = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    config = {
        CONF_SCHEDULE: {CONF_TIME: "07:00", CONF_FERIADOS: ["2026-08-11"]}
    }
    result = next_fire_time(config, now=now)
    assert result == "2026-08-12T07:00:00+00:00"


def test_next_fire_time_respects_already_emitted():
    now = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    config = {CONF_SCHEDULE: {CONF_TIME: "07:00", CONF_SKIP_IF_EMITTED: True}}
    result = next_fire_time(
        config, now=now, last_emitted_date="2026-08-10"
    )
    assert result == "2026-08-11T07:00:00+00:00"


def test_parse_time_accepts_hhmm():
    assert parse_time("06:30") == (6, 30)
    assert parse_time("00:00") == (0, 0)


def test_parse_time_accepts_iso_datetime():
    assert parse_time("2026-08-11T07:30:00") == (7, 30)


def test_parse_time_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        parse_time("not-a-time")


def test_read_alarm_time_static(fake_hass):
    hass, _ = fake_hass()
    assert read_alarm_time(hass, {}) == (7, 0)
    assert read_alarm_time(
        hass, {CONF_SCHEDULE: {CONF_TIME: "06:30"}}
    ) == (6, 30)


def test_read_alarm_time_entity(fake_hass):
    hass, _ = fake_hass(states={"sensor.alarm": type("S", (), {"state": "07:30"})()})
    config = {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}}
    assert read_alarm_time(hass, config) == (7, 30)


def test_read_alarm_time_entity_datetime(fake_hass):
    hass, _ = fake_hass(
        states={"sensor.alarm": type("S", (), {"state": "2026-08-11T07:30:00"})()}
    )
    config = {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}}
    assert read_alarm_time(hass, config) == (7, 30)


def test_read_alarm_time_entity_unavailable(fake_hass):
    hass, _ = fake_hass(
        states={"sensor.alarm": type("S", (), {"state": "unavailable"})()}
    )
    config = {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}}
    assert read_alarm_time(hass, config) is None


def test_read_alarm_time_entity_missing(fake_hass):
    hass, _ = fake_hass()
    config = {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}}
    assert read_alarm_time(hass, config) is None


def test_next_fire_time_accepts_explicit_alarm():
    result = next_fire_time({}, now=_now(), alarm=(6, 30))
    assert result == "2026-08-10T06:30:00+00:00"


def test_async_setup_scheduler_time_entity(fake_hass, fake_trackers):
    hass, _ = fake_hass(
        states={"sensor.alarm": type("S", (), {"state": "07:30"})()}
    )
    scheduler.async_setup_scheduler(
        hass,
        {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}},
        lambda now: None,
    )
    assert fake_trackers.track_calls[-1]["hour"] == 7
    assert fake_trackers.track_calls[-1]["minute"] == 30
    assert fake_trackers.state_change_calls[-1]["entities"] == ["sensor.alarm"]


def test_async_setup_scheduler_reregisters_on_change(
    fake_hass, fake_trackers
):
    hass, _ = fake_hass(
        states={"sensor.alarm": type("S", (), {"state": "07:30"})()}
    )
    scheduler.async_setup_scheduler(
        hass,
        {CONF_SCHEDULE: {CONF_TIME_ENTITY: "sensor.alarm"}},
        lambda now: None,
    )
    before = len(fake_trackers.track_calls)

    hass.state_dict["sensor.alarm"] = type("S", (), {"state": "08:45"})()
    action = fake_trackers.state_change_calls[-1]["action"]
    asyncio.run(action(object()))

    assert len(fake_trackers.track_calls) == before + 1
    assert fake_trackers.track_calls[-1]["hour"] == 8
    assert fake_trackers.track_calls[-1]["minute"] == 45


def test_async_setup_scheduler_without_entity_no_listener(fake_trackers):
    from types import SimpleNamespace

    scheduler.async_setup_scheduler(
        SimpleNamespace(), {CONF_SCHEDULE: {CONF_TIME: "06:30"}}, lambda now: None
    )
    assert fake_trackers.state_change_calls == []


def test_async_setup_scheduler_registers_time(fake_trackers):
    from types import SimpleNamespace

    scheduler.async_setup_scheduler(
        SimpleNamespace(), {CONF_SCHEDULE: {CONF_TIME: "06:30"}}, lambda now: None
    )
    assert fake_trackers.track_calls[-1] == {
        "hour": 6,
        "minute": 30,
        "second": 0,
        "callback": fake_trackers.track_calls[-1]["callback"],
    }


def test_async_setup_configures_scheduler_and_platforms(fake_hass, fake_trackers):
    hass, _ = fake_hass()
    asyncio.run(
        async_setup(hass, {DOMAIN: {"schedule": {CONF_TIME: "06:30"}}})
    )
    assert fake_trackers.track_calls[-1]["hour"] == 6
    assert fake_trackers.track_calls[-1]["minute"] == 30
    assert ("switch", DOMAIN) in fake_trackers.load_platform_calls
    assert ("sensor", DOMAIN) in fake_trackers.load_platform_calls


def test_async_setup_time_entity_arms_at_sensor_time(
    fake_hass, fake_trackers
):
    hass, _ = fake_hass(
        states={"sensor.alarm": type("S", (), {"state": "07:30"})()}
    )
    asyncio.run(
        async_setup(
            hass,
            {DOMAIN: {"schedule": {CONF_TIME_ENTITY: "sensor.alarm"}}},
        )
    )
    assert fake_trackers.track_calls[-1]["hour"] == 7
    assert fake_trackers.track_calls[-1]["minute"] == 30
    assert fake_trackers.state_change_calls[-1]["entities"] == ["sensor.alarm"]


def test_async_setup_time_entity_missing_does_not_arm(fake_hass, fake_trackers):
    hass, _ = fake_hass()
    asyncio.run(
        async_setup(
            hass,
            {DOMAIN: {"schedule": {CONF_TIME_ENTITY: "sensor.alarm"}}},
        )
    )
    assert fake_trackers.track_calls == []


def test_alarm_fires_and_marks_emitted(fake_hass, fake_trackers, monkeypatch):
    from custom_components.buenosdias import coordinator

    runs = []

    async def fake_run(hass, config, emit=True):
        runs.append(emit)
        return {"script": "Hello"}

    monkeypatch.setattr(coordinator, "async_run", fake_run)

    hass, _ = fake_hass()
    asyncio.run(async_setup(hass, {DOMAIN: {}}))
    callback = fake_trackers.track_calls[-1]["callback"]

    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    asyncio.run(callback(now))

    store = hass.data[DOMAIN]["store"]
    assert runs == [True]
    assert store.last_result == "ok"
    assert store.last_emission_date == "2026-08-10"
    assert store.next_alarm is not None


def test_alarm_does_not_fire_when_disabled(fake_hass, fake_trackers, monkeypatch):
    from custom_components.buenosdias import coordinator

    runs = []

    async def fake_run(hass, config, emit=True):
        runs.append(emit)
        return {"script": "Hello"}

    monkeypatch.setattr(coordinator, "async_run", fake_run)

    hass, _ = fake_hass()
    asyncio.run(async_setup(hass, {DOMAIN: {}}))
    hass.data[DOMAIN]["enabled"] = False
    callback = fake_trackers.track_calls[-1]["callback"]

    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    asyncio.run(callback(now))

    assert runs == []