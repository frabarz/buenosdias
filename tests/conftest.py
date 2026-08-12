"""Shared helpers for the buenosdias tests."""

from types import SimpleNamespace

import pytest


class FakeState:
    def __init__(self, state, attributes=None, last_updated=None):
        self.state = state
        self.attributes = attributes or {}
        self.last_updated = last_updated


class FakeStore:
    """Replacement for hass.helpers.storage.Store that records saves."""

    def __init__(self, data=None):
        self.data = data
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved.append(data)


@pytest.fixture(autouse=True)
def fake_trackers(monkeypatch):
    """Patch the heavy HA helpers used by async_setup.

    - ``async_track_utc_time_change``: records the scheduler calls.
    - ``async_track_state_change_event``: records the time_entity listeners.
    - ``discovery.async_load_platform``: records the platform registration.
    Returns both records for the tests to inspect.
    """
    track_calls = []
    load_platform_calls = []
    state_change_calls = []

    def fake_track(hass, callback, hour=None, minute=None, second=None):
        track_calls.append(
            {"hour": hour, "minute": minute, "second": second, "callback": callback}
        )
        return lambda: None

    def fake_track_state_change(hass, entities, action, from_state=None, to_state=None):
        state_change_calls.append({"entities": entities, "action": action})
        return lambda: None

    def fake_load_platform(hass, component, platform, discovered, hass_config):
        load_platform_calls.append((component, platform))
        return None

    monkeypatch.setattr(
        "homeassistant.helpers.event.async_track_utc_time_change", fake_track
    )
    monkeypatch.setattr(
        "homeassistant.helpers.event.async_track_state_change_event",
        fake_track_state_change,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.discovery.async_load_platform", fake_load_platform
    )
    return SimpleNamespace(
        track_calls=track_calls,
        load_platform_calls=load_platform_calls,
        state_change_calls=state_change_calls,
    )


@pytest.fixture
def fake_hass():
    """Return a simplified hass that registers services in `registered`."""

    def _make(states=None):
        registered = {}
        calls = []
        state_dict = dict(states or {})

        def fake_register(domain, service, func, schema=None, supports_response=None):
            registered[(domain, service)] = func

        async def fake_async_call(domain, service, data=None, blocking=False):
            calls.append((domain, service, data or {}))
            return None

        async def fake_async_set(entity_id, state, attributes=None, **kwargs):
            state_dict[entity_id] = FakeState(state, attributes)

        def fake_async_create_task(coro, name=None):
            return coro

        hass = SimpleNamespace(
            data={},
            states=SimpleNamespace(
                get=lambda eid: state_dict.get(eid),
                async_set=fake_async_set,
                as_dict=lambda: dict(state_dict),
            ),
            services=SimpleNamespace(
                async_register=fake_register, async_call=fake_async_call
            ),
            helpers=SimpleNamespace(
                storage=SimpleNamespace(
                    Store=lambda hass, version, key: FakeStore()
                )
            ),
            async_create_task=fake_async_create_task,
        )
        hass.calls = calls
        hass.state_dict = state_dict
        return hass, registered

    return _make
