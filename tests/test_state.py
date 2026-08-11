"""Tests de la persistencia de estado (StateStore)."""

import asyncio

from custom_components.buenosdias.state import StateStore


class _FakeHass:
    pass


def _run(coro):
    return asyncio.run(coro)


def test_state_store_defaults_vacios():
    store = StateStore(_FakeHass(), store=_FakeStore(None))
    assert store.last_emission_date is None
    assert store.last_result is None
    assert store.next_alarm is None


def test_state_store_load_restaura_datos():
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


def test_state_store_load_ignora_no_dict():
    store = StateStore(_FakeHass(), store=_FakeStore("nope"))
    _run(store.async_load())
    assert store.last_emission_date is None


def test_state_store_mark_emitted_persiste():
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


def test_state_store_mark_emitted_con_error():
    store = StateStore(_FakeHass(), store=_FakeStore(None))
    _run(store.async_mark_emitted("2026-08-10", "error: tts roto"))
    assert store.last_result == "error: tts roto"
    assert store.next_alarm is None


class _FakeStore:
    def __init__(self, data):
        self.data = data
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved.append(data)
