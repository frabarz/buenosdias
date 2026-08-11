# Buenos Días

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%E2%89%A5%202025.2-41BDF5)](https://www.home-assistant.io)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Radio matutina personalizada para Home Assistant. Cada mañana recoge contexto
(clima, calendario, sensores y feeds RSS), pide a un LLM que redacte un guion
tipo "radio matutina" y lo emite por altavoz mediante el TTS integrado de HA,
actuando como alarma hablada.

## Overview

`buenosdias` es una `custom_component` (integración de servicio) que vive
dentro del proceso de Home Assistant. No necesita add-ons, contenedores ni
servidores externos:

1. **Contexto** — recolecta el estado de entidades de HA (weather, calendar,
   sensor) y de feeds RSS configurados (noticias y eventos).
2. **Guion** — un LLM redacta el guion hablado. Primario: el agente de
   conversación de HA vía `conversation.async_converse(...)` con
   `extra_system_prompt`. Fallback: endpoint compatible con OpenAI
   (`/chat/completions`).
3. **Emisión** — el texto se envía al TTS integrado de HA (`tts.speak`) sobre
   un `media_player` configurado.
4. **Alarma** — auto-scheduling diario con omisiones (`skip_days`, `feriados`,
   `skip_if_emitted`), estado persistente ("ya emitido") y entidades
   (switch de habilitación + sensores de estado).

## Architecture

Pipeline y módulos:

```
                ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  HA states ───▶│  sources.py  │──▶│  script.py   │──▶│  speak.py    │──▶ TTS
  RSS feeds ───▶│ (contexto)   │   │ (LLM + valid)│   │ (media_player│
                └──────────────┘   └──────────────┘   └──────────────┘
                       ▲                  │  ▲                 │
                       │            coordinator.async_run     │
                       │                  │  └────────────────┘
                 scheduler.py ◀───────────┘
                 (async_track_utc_time_change)
                       │
                  state.py (storage.Store)
                       │
              switch.py / sensor.py (entidades)
```

| Módulo | Responsabilidad |
| --- | --- |
| `sources.py` | Contexto desde `hass.states` + fusión de feeds RSS. |
| `rss.py` | Fetch/parseo/filtrado/dedup de feeds (`feedparser` + `httpx`). |
| `llm.py` | `HAConversationLLM`, `OpenAICompatLLM`, `FallbackLLM`, `build_llm`. |
| `prompts.py` | Plantilla de persona "radio matutina" (texto en español). |
| `script.py` | Generación y validación del guion (no vacío, ≤ `max_chars`, sin markdown, reintento único). |
| `speak.py` | `async_speak`: encendido del `media_player`, volumen y `tts.speak` con `blocking=True`. |
| `coordinator.py` | `async_run(hass, config, emit)` — pipeline contexto → guion → TTS. |
| `state.py` | `StateStore` sobre `hass.helpers.storage.Store` (`last_emission_date`, `last_result`, `next_alarm`). |
| `scheduler.py` | Disparo diario, omisiones y cálculo de próxima alarma. |
| `switch.py` / `sensor.py` | Plataformas de entidades. |

El mínimo soportado de HA es **2025.2** (introduce
`conversation.async_converse(..., extra_system_prompt=...)`, declarado en
`manifest.json`).

## Repository layout

```
flake.nix                     # Flake NixOS (overlay + packages + devShell + checks)
nixos/overlay.nix             # buildHomeAssistantComponent → home-assistant-custom-components.buenosdias
nixos/example.nix             # Ejemplo de uso en un module de NixOS
config.example.yaml           # Configuración YAML de ejemplo documentada
custom_components/buenosdias/ # La integración (código de HA)
tests/                        # Suite pytest
pyproject.toml                # Packaging para desarrollo/venv
```

## Development Setup

Requisitos: Python ≥ 3.13 (lo exige Home Assistant ≥ 2025.2).

**Recomendado (NixOS)** — entorno reproducible con Python 3.14 + HA desde
nixpkgs (sin pip ni toolchains):

```sh
nix develop
pytest -q
```

**Alternativa (venv con pip)**:

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install pytest "homeassistant>=2025.2"
.venv/bin/python -m pytest -q
```

La suite usa un harness ligero (`tests/conftest.py`) con un `fake_hass` que
sustituye a HA (sin eventos reales, sin I/O de red).

## Usage (Internal)

La integración se invoca a través de los servicios de HA:

- `buenosdias.context` — devuelve el contexto recolectado (JSON).
- `buenosdias.generate` — genera el guion sin emitir (dry-run).
- `buenosdias.emit` — pipeline completo: contexto → guion → TTS.

Entidades:

- `switch.buenosdias_enabled` — habilita/deshabilita la alarma.
- `sensor.buenosdias_last_status` — resultado de la última emisión.
- `sensor.buenosdias_next_alarm` — próxima hora de alarma.

## Testing

```sh
.venv/bin/python -m pytest -q
```

111 tests verdes. Los tests se ejecutan también dentro del build Nix
(con `--asyncio-mode=auto` para convivir con el harness de
`pytest-homeassistant-custom-component`).

## Packaging (NixOS)

```sh
nix build .#default          # construye la derivación (corre los tests)
```

El overlay expone `home-assistant-custom-components.buenosdias`; se habilita
en `services.home-assistant.customComponents`. Ver `nixos/example.nix` y
`config.example.yaml`.

## License

Apache-2.0. Ver [LICENSE](LICENSE).
