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
   `skip_if_emitted`), persistent state ("already emitted") and entities
   (enable switch + status sensors).

## Architecture

Pipeline and modules:

```mermaid
flowchart TD
    subgraph Pipeline["coordinator.async_run: daily pipeline"]
        SRC["sources.py<br/>(context)"]
        SCR["script.py<br/>(LLM + validation)"]
        SPK["speak.py<br/>(media_player)"]
        SRC --> SCR --> SPK
    end

    HA["HA entity states"] --> SRC
    RSS["RSS feeds"] --> SRC
    SPK --> TTS["TTS engine"]

    SCHED["scheduler.py<br/>(async_track_utc_time_change)"] -->|triggers| Pipeline
    SCHED -->|reads "already emitted"| ST["state.py<br/>(storage.Store)"]
    Pipeline -->|marks emitted| ST
    ST --> ENT["switch.py / sensor.py<br/>(entities)"]
```

| Module | Responsibility |
| --- | --- |
| `sources.py` | Context from `hass.states` + RSS feed merging. |
| `rss.py` | Feed fetch/parsing/filtering/dedup (`feedparser` + `httpx`). |
| `llm.py` | `HAConversationLLM`, `OpenAICompatLLM`, `FallbackLLM`, `build_llm`. |
| `prompts.py` | "Morning radio" persona template. |
| `script.py` | Script generation and validation (non-empty, ≤ `max_chars`, no markdown, single retry). |
| `speak.py` | `async_speak`: `media_player` power-on, volume and `tts.speak` with `blocking=True`. |
| `coordinator.py` | `async_run(hass, config, emit)` — context → script → TTS pipeline. |
| `state.py` | `StateStore` on top of `hass.helpers.storage.Store` (`last_emission_date`, `last_result`, `next_alarm`). |
| `scheduler.py` | Daily trigger, skip rules and next alarm computation. |
| `switch.py` / `sensor.py` | Entity platforms. |

The minimum supported HA version is **2025.2** (it introduces
`conversation.async_converse(..., extra_system_prompt=...)`, declared in
`manifest.json`).

## Repository layout

```
flake.nix                     # NixOS flake (overlay + packages + devShell + checks)
nixos/overlay.nix             # buildHomeAssistantComponent → home-assistant-custom-components.buenosdias
nixos/example.nix             # Usage example in a NixOS module
config.example.yaml           # Documented example YAML configuration
custom_components/buenosdias/ # The integration (HA code)
tests/                        # pytest suite
pyproject.toml                # Packaging for development/venv
```

## Development Setup

Requirements: Python ≥ 3.13 (required by Home Assistant ≥ 2025.2).

**Recommended (NixOS)** — reproducible environment with Python 3.14 + HA from
nixpkgs (no pip or toolchains):

```sh
nix develop
pytest -q
```

**Alternative (pip venv)**:

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install pytest "homeassistant>=2025.2"
.venv/bin/python -m pytest -q
```

The suite uses a lightweight harness (`tests/conftest.py`) with a `fake_hass`
that substitutes HA (no real events, no network I/O).

## Usage (Internal)

The integration is invoked through HA services:

- `buenosdias.context` — returns the collected context (JSON).
- `buenosdias.generate` — generates the script without playing it (dry-run).
- `buenosdias.emit` — full pipeline: context → script → TTS.

Entities:

- `switch.buenosdias_enabled` — enables/disables the alarm.
- `sensor.buenosdias_last_status` — result of the last playback.
- `sensor.buenosdias_next_alarm` — next alarm time.

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