# Buenos Días

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%E2%89%A5%202025.2-41BDF5)](https://www.home-assistant.io)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

A personalized morning radio for Home Assistant. Every morning it gathers
context (weather, calendar, sensors and RSS feeds), has an LLM write a
"morning radio" script and plays it over your speakers through HA's built-in
TTS, acting as a spoken alarm.

## Overview

`buenosdias` is a `custom_component` (service integration) that lives inside
the Home Assistant process. It needs no add-ons, containers or external
servers:

1. **Context** — collects the state of HA entities (weather, calendar,
   sensor) and configured RSS feeds (news and events).
2. **Script** — an LLM writes the spoken script. Primary: HA's conversation
   agent via `conversation.async_converse(...)` with
   `extra_system_prompt`. Fallback: OpenAI-compatible endpoint
   (`/chat/completions`).
3. **Playback** — the text is sent to HA's built-in TTS (`tts.speak`) on a
   configured `media_player`.
4. **Alarm** — daily auto-scheduling with skip rules (`skip_days`, `feriados`,
   an optional holiday calendar and `skip_if_emitted`), persistent state
   ("already emitted") and entities (enable switch + status sensors).

## Architecture

| Module | Responsibility |
| --- | --- |
| `config_flow.py` | Multi-step UI setup: LLM connection (probed via `GET /models`), plus options menu (TTS, sources, RSS feeds, schedule, persona). Reauth/reconfigure flows. |
| `config_utils.py` | `build_config`: merges entry `data` (credentials win) with `options` into the runtime config validated by `config_schema.py`. |
| `sources.py` | Context from `hass.states` + RSS feed merging. |
| `rss.py` | Feed fetch/parsing/filtering/dedup (`feedparser` + shared `httpx` client). |
| `llm.py` | `HAConversationLLM`, `OpenAICompatLLM`, `FallbackLLM`, `build_llm`. |
| `prompts.py` | "Morning radio" persona template. |
| `script.py` | Script generation and validation (non-empty, ≤ `max_chars`, no markdown, single retry). |
| `speak.py` | `async_speak`: `media_player` power-on, volume and `tts.speak` with `blocking=True`. |
| `coordinator.py` | `async_run(hass, config, emit)` — context → script → TTS pipeline. |
| `state.py` | `StateStore` on top of `homeassistant.helpers.storage.Store` (`last_emission_date`, `last_result`, `next_alarm`, `last_script`). |
| `scheduler.py` | Daily trigger, skip rules, `time_entity`, holiday resolution and next alarm computation. |
| `switch.py` / `sensor.py` | Entity platforms. |

The minimum supported HA version is **2025.2** (it introduces
`conversation.async_converse(..., extra_system_prompt=...)`, declared in
`manifest.json`).

## Repository layout

```
flake.nix                     # NixOS flake (overlay + packages + devShell + checks)
nixos/overlay.nix             # buildHomeAssistantComponent → home-assistant-custom-components.buenosdias
nixos/example.nix             # Usage example in a NixOS module
config.example.yaml           # Legacy YAML config (deprecated migration path only)
custom_components/buenosdias/ # The integration (HA code)
tests/                        # pytest suite
pyproject.toml                # Packaging for development/venv
CURSED_KNOWLEDGE.md           # Integration-specific pitfalls we learned the hard way
```

## Development Setup

Requirements: Python ≥ 3.13 (required by Home Assistant ≥ 2025.2).

**Recommended (NixOS)** — reproducible environment with Python 3.14 + HA from
nixpkgs (no pip or toolchains):

```sh
nix develop
pytest -q
```

**Alternative (uv)**:

```sh
uv venv .venv
.venv/bin/uv pip install -e .
.venv/bin/uv pip install pytest "homeassistant>=2025.2"
.venv/bin/uv run python -m pytest -q
```

The suite combines a lightweight harness (`tests/conftest.py`) with a
`fake_hass` for unit-level tests, and `pytest-homeassistant-custom-component`
for real `hass` fixtures that exercise the config flow end to end.

## Usage

Configuration is done through a **UI config flow** (Settings → Devices &
Services → Add Integration → "Buenos Días"). The initial steps capture the
**LLM connection**: pick a conversation agent or an OpenAI-compatible endpoint
(base URL + model + API key, validated with a live `GET /models` probe). The
**options flow** then tunes everything else, section by section: TTS, sources
(weather, calendar, sensors), RSS feeds (add/edit/remove inline), the schedule
and the persona. The API key stays in the entry `data` and is never logged or
exposed via options.

Changing the LLM connection later is done from the integration's "Reconfigure
entry" menu; if the stored key gets rejected, the integration automatically
starts a **reauthentication flow** (see `_async_notify_reauth` in
`__init__.py`).

Legacy YAML (`config.example.yaml`) is deprecated: a `buenosdias:` block only
triggers a one-time import into a config entry at startup (see `async_setup`
in `__init__.py` and `async_step_import` in `config_flow.py`). Remove it once
the entry exists.

The integration is then invoked through HA services:

- `buenosdias.context` — returns the collected context (JSON).
- `buenosdias.generate` — generates the script without playing it (dry-run).
- `buenosdias.emit` — full pipeline: context → script → TTS.

Entities (all grouped under the "Buenos Días" device):

- `switch.buenos_dias_enabled` — enables/disables the alarm.
- `sensor.buenos_dias_last_status` — result of the last playback.
- `sensor.buenos_dias_next_alarm` — next alarm time.
- `sensor.buenos_dias_last_script` — last generated radio script.

## Testing

```sh
.venv/bin/python -m pytest -q
```

All tests pass. They also run inside the Nix build (with `--asyncio-mode=auto`
so it coexists with the `pytest-homeassistant-custom-component` harness).

## Packaging (NixOS)

```sh
nix build .#default          # builds the derivation (runs the tests)
```

The overlay exposes `home-assistant-custom-components.buenosdias`; enable it
in `services.home-assistant.customComponents`. See `nixos/example.nix` and
`config.example.yaml`.

## License

Apache-2.0. See [LICENSE](LICENSE).
