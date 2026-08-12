"""Tests of the state persistence (StateStore)."""

import asyncio

from custom_components.buenosdias.state import StateStore


class _FakeHass:
    pass


def _run(coro):
    return asyncio.run(coro)


def test_state_store_defaults_empty():
    store = StateStore(_FakeHass(), store=_FakeStore(None))
    assert store.last_emission_date is None
    assert store.last_result is None
    assert store.next_alarm is None


def test_state_store_load_restores_data():
    store = StateStore(
        _FakeHass(),
        store=_FakeStore(
            {
                "last_emission_date": "2026-08-10",
                "last_result": "ok",
                "next_alarm": "2026-08-11T05:00:00+00:00",
            }
        ),
    )
    _run(store.async_load())
    assert store.last_emission_date == "2026-08-10"
    assert store.last_result == "ok"
    assert store.next_alarm == "2026-08-11T05:00:00+00:00"


def test_state_store_load_ignores_non_dict():
    store = StateStore(_FakeHass(), store=_FakeStore("nope"))
    _run(store.async_load())
    assert store.last_emission_date is None


def test_state_store_mark_emitted_persists():
    fake_store = _FakeStore(None)
    store = StateStore(_FakeHass(), store=fake_store)
    _run(store.async_mark_emitted("2026-08-10", "ok", "2026-08-11T05:00:00+00:00"))
    assert store.last_emission_date == "2026-08-10"
    assert store.last_result == "ok"
    assert store.next_alarm == "2026-08-11T05:00:00+00:00"
    assert fake_store.saved == [
        {
            "last_emission_date": "2026-08-10",
            "last_result": "ok",
            "next_alarm": "2026-08-11T05:00:00+00:00",
        }
    ]


def test_state_store_mark_emitted_with_error():
    store = StateStore(_FakeHass(), store=_FakeStore(None))
    _run(store.async_mark_emitted("2026-08-10", "error: tts broken"))
    assert store.last_result == "error: tts broken"
    assert store.next_alarm is None


class _FakeStore:
    def __init__(self, data):
        self.data = data
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved.append(data)