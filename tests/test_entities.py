"""Tests of the switch and sensor entities."""

import asyncio

from conftest import FakeStore
from custom_components.buenosdias.const import DOMAIN
from custom_components.buenosdias.sensor import (
    BuenosdiasLastStatusSensor,
    BuenosdiasNextAlarmSensor,
)
from custom_components.buenosdias.state import StateStore
from custom_components.buenosdias.switch import BuenosdiasEnabledSwitch


def _run(coro):
    return asyncio.run(coro)


def _make_switch(hass, monkeypatch):
    switch = BuenosdiasEnabledSwitch(hass)
    monkeypatch.setattr(switch, "async_write_ha_state", lambda: None)
    return switch


def test_switch_starts_enabled(fake_hass, monkeypatch):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": True}
    switch = _make_switch(hass, monkeypatch)
    assert switch.is_on is True
    assert switch.unique_id == "buenosdias_enabled"


def test_switch_turn_off_disables(fake_hass, monkeypatch):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": True}
    switch = _make_switch(hass, monkeypatch)
    _run(switch.async_turn_off())
    assert switch.is_on is False
    assert hass.data[DOMAIN]["enabled"] is False


def test_switch_turn_on_enables(fake_hass, monkeypatch):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": False}
    switch = _make_switch(hass, monkeypatch)
    assert switch.is_on is False
    _run(switch.async_turn_on())
    assert switch.is_on is True
    assert hass.data[DOMAIN]["enabled"] is True


def test_sensor_last_status_without_emissions(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store)
    assert sensor.native_value == "never"
    assert sensor.unique_id == "buenosdias_last_status"


def test_sensor_last_status_after_emission(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store)
    _run(store.async_mark_emitted("2026-08-10", "ok", "2026-08-11T05:00:00+00:00"))
    sensor.refresh_from_store()
    assert sensor.native_value == "ok"
    assert sensor.extra_state_attributes["last_emission_date"] == "2026-08-10"
    assert sensor.extra_state_attributes["next_alarm"] == "2026-08-11T05:00:00+00:00"


def test_sensor_next_alarm_unscheduled(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasNextAlarmSensor(hass, store)
    assert sensor.native_value == "not_scheduled"
    assert sensor.unique_id == "buenosdias_next_alarm"


def test_sensor_next_alarm_scheduled(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasNextAlarmSensor(hass, store)
    _run(store.async_mark_emitted("2026-08-10", "ok", "2026-08-11T05:00:00+00:00"))
    sensor.refresh_from_store()
    assert sensor.native_value == "2026-08-11T05:00:00+00:00"