# Buenos Días — Guía rápida

Radio matutina personalizada para Home Assistant: contexto + LLM + TTS como
alarma hablada, sin servicios externos.

## Quick Start

1. Copia `custom_components/buenosdias/` a tu `custom_components/`.
2. Añade el bloque `buenosdias:` a tu `configuration.yaml` (ejemplo completo en
   [config.example.yaml](config.example.yaml)).
3. Reinicia HA. Desde Developer Tools → Services prueba:

   - `buenosdias.generate` — genera el guion (dry-run).
   - `buenosdias.emit` — recoge contexto, genera y emite por el altavoz.

## Requirements

- Home Assistant **≥ 2025.2**
- Un **agente de conversación** configurado (p. ej. `conversation.assist`) o un
  endpoint compatible con OpenAI (`/chat/completions`).
- Un **motor TTS** y un **media_player** (p. ej. Piper + altavoz).

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
      nixosConfigurations.mi = nixpkgs.lib.nixosSystem {
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

Ejemplo mínimo:

```yaml
buenosdias:
  llm:
    mode: ha_conversation          # o "openai_compatible"
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

Claves API siempre por `!secret` (ver `config.example.yaml`).

## Services

| Servicio | Descripción |
| --- | --- |
| `buenosdias.context` | Contexto recolectado (clima, calendario, sensores, RSS) en JSON. |
| `buenosdias.generate` | Genera el guion con el LLM (dry-run), devuelve el texto. |
| `buenosdias.emit` | Pipeline completo: contexto → guion → TTS en el media_player. |

## Entities

| Entidad | Descripción |
| --- | --- |
| `switch.buenosdias_enabled` | Pausa/reanuda la alarma diaria. |
| `sensor.buenosdias_last_status` | Resultado de la última emisión (`ok` / error) y fecha. |
| `sensor.buenosdias_next_alarm` | Próxima hora de alarma (ISO-8601). |
