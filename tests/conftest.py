"""Shared helpers for the buenosdias tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir, request):
    """Point the HA test instance at this repo's custom_components."""
    repo_components = Path(__file__).resolve().parent.parent / "custom_components"
    target = Path(hass_tmp_config_dir) / "custom_components" / "buenosdias"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(repo_components / "buenosdias", target_is_directory=True)
    return hass_tmp_config_dir


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

    - ``async_track_time_change``: records the scheduler calls.
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
        "homeassistant.helpers.event.async_track_time_change", fake_track
    )
    monkeypatch.setattr(
        "homeassistant.helpers.event.async_track_state_change_event",
        fake_track_state_change,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.discovery.async_load_platform", fake_load_platform
    )

    def fake_store_factory(hass, version, key):
        return FakeStore()

    monkeypatch.setattr("custom_components.buenosdias.state.Store", fake_store_factory)
    return SimpleNamespace(
        track_calls=track_calls,
        load_platform_calls=load_platform_calls,
        state_change_calls=state_change_calls,
    )


class FakeEntry:
    """Minimal config entry stub."""

    def __init__(self, entry_id="entry-1", domain="buenosdias", data=None, options=None):
        self.entry_id = entry_id
        self.domain = domain
        self.data = data or {}
        self.options = options or {}
        self.listeners = []
        self.reauth_started = False

    def add_update_listener(self, callback):
        self.listeners.append(callback)

    def async_start_reauth(self, hass, context=None, data=None):
        self.reauth_started = True


@pytest.fixture
def fake_hass():
    """Return a simplified hass that registers services in `registered`."""

    def _make(states=None):
        registered = {}
        calls = []
        state_dict = dict(states or {})
        entries = []

        def fake_register(domain, service, func, schema=None, supports_response=None):
            registered[(domain, service)] = func

        async def fake_async_call(domain, service, data=None, blocking=False):
            calls.append((domain, service, data or {}))
            return None

        async def fake_async_set(entity_id, state, attributes=None, **kwargs):
            state_dict[entity_id] = FakeState(state, attributes)

        def fake_async_create_task(coro, name=None):
            return coro

        def fake_async_remove(domain, service):
            registered.pop((domain, service), None)

        def fake_has_entries(domain):
            return any(getattr(e, "domain", None) == domain for e in entries)

        async def fake_forward_entry_setups(entry, platforms):
            calls.append(("__forward__", entry.entry_id, list(platforms)))

        async def fake_unload_platforms(entry, platforms):
            calls.append(("__unload__", entry.entry_id, list(platforms)))

        async def fake_reload(entry_id):
            calls.append(("__reload__", entry_id))

        config_entries_calls = []

        def fake_flow_init(*args, **kwargs):
            config_entries_calls.append(("__flow_init__", args, kwargs))
            return None

        config_entries = SimpleNamespace(
            entries=entries,
            async_has_entries=fake_has_entries,
            async_forward_entry_setups=fake_forward_entry_setups,
            async_unload_platforms=fake_unload_platforms,
            async_reload=fake_reload,
            flow=SimpleNamespace(async_init=fake_flow_init),
            _calls=config_entries_calls,
        )

        hass = SimpleNamespace(
            data={},
            states=SimpleNamespace(
                get=lambda eid: state_dict.get(eid),
                async_set=fake_async_set,
                as_dict=lambda: dict(state_dict),
            ),
            services=SimpleNamespace(
                async_register=fake_register,
                async_call=fake_async_call,
                async_remove=fake_async_remove,
            ),
            helpers=SimpleNamespace(
                storage=SimpleNamespace(
                    Store=lambda hass, version, key: FakeStore()
                )
            ),
            config_entries=config_entries,
            async_create_task=fake_async_create_task,
        )
        hass.calls = calls
        hass.state_dict = state_dict
        hass.registered = registered
        return hass, registered

    return _make
