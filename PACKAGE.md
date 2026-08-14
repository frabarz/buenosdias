# Buenos Días — Quick Guide

A personalized morning radio for Home Assistant: context + LLM + TTS as a
spoken alarm, with no external services.

## Quick Start

1. Copy `custom_components/buenosdias/` to your `custom_components/` (or use
   the NixOS flake below) and restart HA.
2. **Settings → Devices & Services → Add Integration → "Buenos Días"**, fill in
   the LLM connection, then open Options to tune TTS, sources, schedule and
   persona.
3. From Developer Tools → Services try:

   - `buenosdias.generate` — generates the script (dry-run).
   - `buenosdias.emit` — gathers context, generates and plays it over the
     speaker.

> **Migrating from YAML?** v0.2.0 dropped YAML configuration. A legacy
> `buenosdias:` block in `configuration.yaml` now only triggers a one-time
> import into a config entry at startup. Keep it, restart HA, confirm the
> import dialog, then remove the block and finish the setup in the UI.

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

Setup is done through the **UI config flow**. The initial form asks for the
LLM connection (`ha_conversation` agent or an OpenAI-compatible endpoint). The
**Options** menu then covers, section by section:

- **LLM** — max chars per script, and the connection itself.
- **TTS** — TTS engine, media player, language, volume, restore volume.
- **Sources** — weather, calendar and sensor entities, plus RSS feeds.
- **Schedule** — alarm time (or a `time_entity`), skip days, `feriados`,
  `skip_if_emitted`.
- **Persona** — free-text prompt controlling the script's language and style.

API keys are stored in the config entry `data` (never in options, never
logged). The full equivalent of the old YAML block is shown in
[config.example.yaml](config.example.yaml) purely as an import/migration
reference.

## Language

The script is written in whatever language and style your **persona** defines.
Set the persona in the integration **Options → Persona** to control it, e.g. a
Spanish persona produces a Spanish morning show:

> Eres el locutor de una radio matutina. Habla en español de España, con tono
> cercano y natural. Redacta un breve guion hablado.

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