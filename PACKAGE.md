# Buenos Días

Buenos Días is a morning radio that lives in Home Assistant. At your alarm time it gathers what matters for today, asks an LLM to turn it into a short spoken script, and plays it on your speakers. No extra server, no cloud dependency.

## What it does for you

- You wake to a briefing that fits your day, not a generic beep.
- You can keep the conversation agent you already use in HA, or point it at any OpenAI compatible endpoint such as Ollama, OpenRouter, Groq or LM Studio.
- You choose the sources. Pick weather, calendar and sensor entities, and add RSS feeds for news and events. The integration filters by age, caps items, drops duplicates and skips entries that match your exclude keywords. Exclude ignores accents, so `futbol` matches `fútbol`.
- You control the schedule. Use a fixed time such as `07:00` or point `time_entity` at a sensor that holds your phone alarm. Skip weekends, specific `feriados` dates, a holiday calendar, and tell it not to repeat if it already fired today.
- You set the persona. Write the prompt in the language and tone you want to hear. Spanish, English, terse, warm, funny, it follows you.
- TTS behaves. It wakes the player, sets the volume, plays, then puts the volume back if you want.

## You need

- Home Assistant 2025.2 or newer
- An LLM, either a conversation agent set up in HA, or an OpenAI compatible endpoint that serves `/chat/completions`
- A TTS engine such as Piper and a media player with a speaker

## Install

### HACS

In HACS go to Integrations, open the menu, add `https://github.com/frabarz/buenosdias` as a custom repository (type Integration), install, restart Home Assistant.

### Manual

Copy `custom_components/buenosdias` into `<config>/custom_components` and restart.

### NixOS

The flake exposes `home-assistant-custom-components.buenosdias`:

```nix
{
  inputs.buenosdias.url = "github:frabarz/buenosdias";
  outputs = { self, nixpkgs, buenosdias, ... }: {
    nixosConfigurations.my = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        buenosdias.nixosModules.default
        { services.home-assistant.customComponents = [ buenosdias.packages.x86_64-linux.default ]; }
      ];
    };
  };
}
```

## First run

1. Open Settings, Devices & Services, Add Integration, pick Buenos Días. Choose how it will talk to the LLM. The form checks the endpoint with `GET /models` before it saves. HA stores the API key in the config entry and never shows it again.
2. Open Configure to finish setup. You will find LLM, TTS, Sources, RSS feeds and Schedule. Persona lives inside LLM. Work through them in order.
3. Try it without waiting for morning. Open Developer Tools, Services, run `buenosdias.generate` to preview the text, then `buenosdias.emit` to hear it.

## Configuration

All of it lives in the UI. No YAML needed.

LLM connection happens during setup. You can change it later with Reconfigure. Two choices:

- Home Assistant conversation agent. Pick an agent entity. This is the easiest path if you already use Assist with Ollama or OpenAI in HA.
- OpenAI compatible endpoint. Set `base_url`, `model` and `api_key`. If HA later rejects the key, Buenos Días opens a reauthentication dialog on its own. If you do not run a local model, OpenRouter has free models that work well here. The integration makes one call each morning, two at most if the first draft runs long and needs a retry, so a free tier stretches far.

The rest lives under Configure:

- LLM. Set `max_chars` to cap the spoken text, 100 to 20000, default 2000. If the script runs long, the integration asks the model to shorten it once. Persona also lives here as free text that controls language and style.
- TTS. Choose the TTS entity and media player, language such as `es-ES`, volume from 0 to 1, and whether to restore volume after playback.
- Sources. Pick which weather, calendar and sensor entities to include each morning.
- RSS feeds. Add, edit or remove feeds inline. For each feed you set `kind` (news or events), `max_age_hours`, `max_items`, `tags` as free labels, and `exclude` keywords to skip.
- Schedule. Set a fixed `time` (`07:00` or `HH:MM:SS`) or a `time_entity` that the integration follows and re-arms when it changes. Add `skip_days` (mon to sun), `feriados` as fixed `YYYY-MM-DD` dates, an optional holiday calendar entity, and `skip_if_emitted` to avoid a second firing on the same day.

### Persona examples

Spanish morning show:

> Eres el locutor de una radio matutina. Habla en español de España, con tono cercano y natural. Puedes incluir un toque de humor pero sé informativo.

English, concise:

> You are a friendly morning radio host. Speak in clear, warm English. Keep it brief and upbeat. Highlight what matters today.

## Using it

You can let the daily alarm run it, or call it yourself.

- `buenosdias.context` shows the JSON the LLM will see.
- `buenosdias.generate` writes the script without playing it. Good for tuning the persona.
- `buenosdias.emit` does the full run, context to script to speaker.

Call `emit` from an automation, a dashboard button, or Developer Tools.

Entities sit under the Buenos Días device:

- `switch.buenos_dias_enabled` pauses or resumes the daily alarm.
- `sensor.buenos_dias_last_status` holds `ok` or an error from the last run. The full last script is in its `last_script` attribute, so you can read it with `{{ state_attr('sensor.buenos_dias_last_status','last_script') }}`.
- `sensor.buenos_dias_next_alarm` shows when the next alarm will fire, in UTC, or `not_scheduled`.

Tip: point `time_entity` at `sensor.your_phone_next_alarm` if your phone exposes it. The integration tracks that sensor and re-registers the alarm when it changes.

## Migrating from YAML

YAML with `buenosdias:` in `configuration.yaml` is deprecated. It now does a one-time import into a config entry at startup. If you have it, keep the block, restart, confirm the import dialog, then remove the block and finish tuning in the UI. New installs should skip YAML and use the UI from the start. See `config.example.yaml` for the old structure.

## Need help

Open an issue at [github.com/frabarz/buenosdias/issues](https://github.com/frabarz/buenosdias/issues). For development details see the [README](README.md).
