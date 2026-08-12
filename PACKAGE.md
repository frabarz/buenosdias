# Buenos Días — Quick Guide

A personalized morning radio for Home Assistant: context + LLM + TTS as a
spoken alarm, with no external services.

## Quick Start

1. Copy `custom_components/buenosdias/` to your `custom_components/`.
2. Add the `buenosdias:` block to your `configuration.yaml` (full example in
   [config.example.yaml](config.example.yaml)).
3. Restart HA. From Developer Tools → Services try:

   - `buenosdias.generate` — generates the script (dry-run).
   - `buenosdias.emit` — gathers context, generates and plays it over the
     speaker.

## Requirements

- Home Assistant **≥ 2025.2**
- A **conversation agent** configured (e.g. `conversation.assist`) or an
  OpenAI-compatible endpoint (`/chat/completions`).
- A **TTS engine** and a **media_player** (e.g. Piper + speaker).

## Installation

### Manual (HACS / custom_components)

```sh
git clone https://tangled.org/frabarz.cl/buenosdias buenosdias
cp -r buenosdias/custom_components/buenosdias <hass_config>/custom_components/
```

### NixOS (flake)

```nix
{
  inputs.buenosdias.url = "git+https://tangled.org/frabarz.cl/buenosdias.git";
  outputs = { self, nixpkgs, buenosdias, ... }:
    let system = "x86_64-linux"; in {
      nixosConfigurations.my = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          buenosdias.nixosModules.default
          { services.home-assistant.customComponents = [ buenosdias.packages.${system}.default ]; }
        ];
      };
    };
}
```

## Configuration

Minimal example:

```yaml
buenosdias:
  llm:
    mode: ha_conversation          # or "openai_compatible"
  tts:
    entity_id: tts.piper
    media_player: media_player.sala
    language: es-ES
  sources:
    weather: [weather.casa]
    calendar: [calendar.familia]
  schedule:
    time: "07:00"
    skip_days: [sat, sun]
```

API keys always via `!secret` (see `config.example.yaml`).

## Language

The script is written in whatever language and style your **persona** defines.
Set `buenosdias.persona` in your configuration to control it, e.g. a Spanish
persona produces a Spanish morning show:

```yaml
buenosdias:
  persona: |
    Eres el locutor de una radio matutina. Habla en español de España, con
    tono cercano y natural. Redacta un breve guion hablado.
```

## Services

| Service | Description |
| --- | --- |
| `buenosdias.context` | Collected context (weather, calendar, sensors, RSS) as JSON. |
| `buenosdias.generate` | Generates the script with the LLM (dry-run), returns the text. |
| `buenosdias.emit` | Full pipeline: context → script → TTS on the media_player. |

## Entities

| Entity | Description |
| --- | --- |
| `switch.buenosdias_enabled` | Pauses/resumes the daily alarm. |
| `sensor.buenosdias_last_status` | Result of the last playback (`ok` / error) and date. |
| `sensor.buenosdias_next_alarm` | Next alarm time (ISO-8601). |