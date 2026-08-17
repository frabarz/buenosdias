# Buenos Días — Quick Guide

A personalized morning radio for Home Assistant: context + LLM + TTS as a
spoken alarm, with no external services.

## Quick Start

1. Copy `custom_components/buenosdias/` to your `custom_components/` (or use
   the NixOS flake below) and restart HA.
2. **Settings → Devices & Services → Add Integration → "Buenos Días"**, fill
   in the LLM connection, then use the Options menu to tune the rest.
3. From Developer Tools → Services try:

   - `buenosdias.generate` — generates the script (dry-run).
   - `buenosdias.emit` — gathers context, generates and plays it over the
     speaker.

> **Migrating from YAML?** YAML configuration is deprecated. A legacy
> `buenosdias:` block in `configuration.yaml` only triggers a one-time import
> into a config entry at startup. Keep it, restart HA, confirm the import
> dialog, then remove the block and finish the setup in the UI.

## Requirements

- Home Assistant **≥ 2025.2**
- A **conversation agent** configured (e.g. `conversation.assist`) or an
  OpenAI-compatible endpoint (`/chat/completions`).
- A **TTS engine** and a **media_player** (e.g. Piper + speaker).

## Installation

### Manual (HACS / custom_components)

```sh
git clone https://github.com/frabarz/buenosdias buenosdias
cp -r buenosdias/custom_components/buenosdias <hass_config>/custom_components/
```

### NixOS (flake)

```nix
{
  inputs.buenosdias.url = "github:frabarz/buenosdias";
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

Setup is done through the **UI config flow**, in two parts:

1. **LLM connection** (config flow): choose a Home Assistant conversation
   agent, or an OpenAI-compatible endpoint (base URL, model, API key). The
   endpoint is validated with a live probe before it is saved. The API key is
   stored in the entry `data` and is never logged or exposed again.
2. **Options menu** (Config Flow → Options), section by section:

- **LLM** — maximum script length (`max_chars`, 100–20000).
- **TTS** — TTS engine, media player, language, volume, restore volume.
- **Sources** — weather, calendar and sensor entities.
- **RSS feeds** — add/edit/remove feeds inline; per feed set kind
  (news/events), `max_age_hours`, `max_items`, `tags` and `exclude`
  keywords.
- **Schedule** — alarm time (or a `time_entity` to read it dynamically,
  HH:MM or HH:MM:SS accepted), skip days, `feriados`, an optional holiday
  calendar and `skip_if_emitted`.
- **Persona** — free-text prompt controlling the script's language and style.

To change the LLM connection later, use the integration's **Reconfigure
entry** menu; if the stored API key is rejected, a reauthentication dialog is
started automatically. The full equivalent of the old YAML block is shown in
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
| `switch.buenos_dias_enabled` | Pauses/resumes the daily alarm. |
| `sensor.buenos_dias_last_status` | Result of the last playback (`ok` / error) and date. |
| `sensor.buenos_dias_next_alarm` | Next alarm time (ISO-8601). |

All entities are grouped under the "Buenos Días" device.