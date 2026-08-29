"""Tests of the switch and sensor entities."""

import asyncio

from conftest import FakeEntry, FakeStore
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
    switch = BuenosdiasEnabledSwitch(hass, FakeEntry())
    monkeypatch.setattr(switch, "async_write_ha_state", lambda: None)
    return switch


def test_switch_starts_enabled(fake_hass, monkeypatch):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": True}
    switch = _make_switch(hass, monkeypatch)
    assert switch.is_on is True
    assert switch.unique_id == "buenosdias_enabled"
    assert switch.translation_key == "enabled"


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


def test_switch_icon_reflects_state(fake_hass, monkeypatch):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": True}
    switch = _make_switch(hass, monkeypatch)
    assert switch.icon == "mdi:alarm"
    _run(switch.async_turn_off())
    assert switch.icon == "mdi:alarm-off"


def test_sensor_last_status_without_emissions(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store, FakeEntry())
    assert sensor.native_value == "never"
    assert sensor.unique_id == "buenosdias_last_status"
    assert sensor.translation_key == "last_status"


def test_sensor_last_status_after_emission(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store, FakeEntry())
    _run(store.async_mark_emitted("2026-08-10", "ok", "2026-08-11T05:00:00+00:00"))
    sensor.refresh_from_store()
    assert sensor.native_value == "ok"
    assert sensor.extra_state_attributes["last_emission_date"] == "2026-08-10"
    assert sensor.extra_state_attributes["next_alarm"] == "2026-08-11T05:00:00+00:00"


def test_sensor_next_alarm_unscheduled(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasNextAlarmSensor(hass, store, FakeEntry())
    assert sensor.native_value == "not_scheduled"
    assert sensor.unique_id == "buenosdias_next_alarm"
    assert sensor.translation_key == "next_alarm"


def test_sensor_next_alarm_scheduled(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasNextAlarmSensor(hass, store, FakeEntry())
    _run(store.async_mark_emitted("2026-08-10", "ok", "2026-08-11T05:00:00+00:00"))
    sensor.refresh_from_store()
    assert sensor.native_value == "2026-08-11T05:00:00+00:00"


def test_sensor_last_script_attribute_without_scripts(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store, FakeEntry())
    assert sensor.native_value == "never"
    assert sensor.extra_state_attributes["last_script"] is None


def test_sensor_last_script_attribute_after_generation(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store, FakeEntry())
    _run(store.async_set_last_script("Buenos días, hoy hace sol."))
    sensor.refresh_from_store()
    assert sensor.extra_state_attributes["last_script"] == "Buenos días, hoy hace sol."


def test_sensor_last_script_attribute_keeps_full_long_script(fake_hass):
    hass, _ = fake_hass()
    store = StateStore(hass, store=FakeStore(None))
    sensor = BuenosdiasLastStatusSensor(hass, store, FakeEntry())
    long_script = "Buenos días y feliz mañana. " * 50
    _run(store.async_set_last_script(long_script))
    sensor.refresh_from_store()
    assert sensor.extra_state_attributes["last_script"] == long_script


def test_entities_share_device(fake_hass):
    hass, _ = fake_hass()
    hass.data[DOMAIN] = {"enabled": True}
    store = StateStore(hass, store=FakeStore(None))
    entry = FakeEntry(entry_id="entry-device")
    switch = BuenosdiasEnabledSwitch(hass, entry)
    last_status = BuenosdiasLastStatusSensor(hass, store, entry)
    next_alarm = BuenosdiasNextAlarmSensor(hass, store, entry)
    for entity in (switch, last_status, next_alarm):
        assert entity.device_info["identifiers"] == {(DOMAIN, "entry-device")}
        assert entity.has_entity_name is True
