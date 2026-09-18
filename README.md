# Buenos Días

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%E2%89%A5%202025.2-41BDF5)](https://www.home-assistant.io)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Buenos Días is a morning radio for Home Assistant. It gathers your weather, calendar, sensors and RSS, hands that context to an LLM, and plays the resulting script on your speakers with `tts.speak`. It runs as a `custom_component` inside Home Assistant, so you do not need an extra container or add-on.

If you want to install and use it, the guide in [PACKAGE.md](PACKAGE.md) has the steps. This readme is for contributors.

## How it works

The pipeline has four parts. Sources collect context, the LLM writes the script, TTS plays it, scheduler decides when to fire.

Sources handle context. `sources.py` reads the entities you selected and `rss.py` fetches feeds. That module uses `feedparser` and the shared HA `httpx` client, then drops duplicates and filters by age and keywords.

Script handles text. `llm.py` offers two ways to call a model. `HAConversationLLM` uses `conversation.async_converse` with `extra_system_prompt`, which needs HA 2025.2 or newer. `OpenAICompatLLM` talks to any `/chat/completions` endpoint. `FallbackLLM` tries one and falls back to the other. `prompts.py` and `script.py` keep the output spoken only, no markdown, capped at `max_chars`, with one retry to shorten it. That keeps cost low. The alarm fires once a day, so most mornings you get one call and a second only if the first draft runs long. Providers like OpenRouter have free models that are enough to try it out.

Playback handles audio. `speak.py` turns the `media_player` on when it can, sets the volume, calls `tts.speak` with `blocking=True`, and restores the old volume if you asked it to.

Alarm handles timing. `scheduler.py` decides if it should fire today and when the next alarm is. It respects `skip_days`, `feriados`, a holiday calendar, `skip_if_emitted`, and a `time_entity` that can follow a sensor instead of a fixed `time`. `state.py` persists `last_emission_date`, `last_result`, `next_alarm` and `last_script` through `homeassistant.helpers.storage.Store`. `switch.py` and `sensor.py` expose the switch and sensors.

The module docstrings hold the details, start with `custom_components/buenosdias/__init__.py:1`.

## Hacking

You need Python 3.13 or newer and HA 2025.2 or newer. Runtime deps are `feedparser` and `httpx`.

With Nix you get a reproducible shell and no pip setup:

```sh
nix develop
pytest -q          # 185 tests, no extra flags
nix build .#default  # also runs the suite with --asyncio-mode=auto
```

Without Nix:

```sh
uv venv .venv
.venv/bin/uv pip install -e ".[dev]"
.venv/bin/uv run pytest -q --asyncio-mode=auto
```

Tests use two harnesses. A small `fake_hass` covers unit tests and the real `hass` fixture from `pytest-homeassistant-custom-component` covers the config flow. That split is set up in `tests/conftest.py:1`.

Layout is small. `custom_components/buenosdias` is the integration, `tests` holds the suite, `nixos/overlay.nix` packages it with `buildHomeAssistantComponent`, and `config.example.yaml` is the old YAML path that now migrates once into a config entry.

`CURSED_KNOWLEDGE.md` collects traps we hit, like why you must unsubscribe from `add_update_listener` on unload.

## License

Apache-2.0, see [LICENSE](LICENSE).
