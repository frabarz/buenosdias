{
  config,
  pkgs,
  lib,
  ...
}:
let
  overlay = import ./overlay.nix;
in
{
  imports = [ ];
  nixpkgs.overlays = [ overlay ];

  services.home-assistant = {
    enable = true;
    # Puedes añadir más componentes, p. ej. [ "frigate" "buenosdias" ].
    customComponents = [ pkgs.home-assistant-custom-components.buenosdias ];

    config = {
      # Configuración base de HA.
      default_config = { };

      # Bloque de configuración de la integración buenosdias.
      # Secretos (api_key) solo vía !secret, ver config.example.yaml.
      buenosdias = {
        llm = {
          mode = "ha_conversation";
          # agent = "conversation.assist";   # opcional
          max_chars = 2000;
          openai = {
            base_url = "http://localhost:11434/v1";
            api_key = "!secret buenosdias_llm_api_key";
            model = "llama3";
          };
        };

        tts = {
          entity_id = "tts.piper";
          media_player = "media_player.sala";
          language = "es-ES";
          volume = 0.6;
          restore_volume = true;
        };

        sources = {
          weather = [ "weather.casa" ];
          calendar = [ "calendar.familia" ];
          sensors = [ "sensor.consumo_diario" ];
          rss.feeds = [
            {
              url = "https://www.ejemplo.org/noticias/rss.xml";
              kind = "news";
              max_age_hours = 24;
              max_items = 5;
            }
          ];
        };

        schedule = {
          time = "07:00";
          # time_entity = "sensor.alarma_telefono";   # hora dinámica desde una entidad
          skip_days = [
            "sat"
            "sun"
          ];
          feriados = [ "2026-01-01" ];
          skip_if_emitted = true;
        };

        persona = ''
          Eres el locutor de una radio matutina. Habla en español de España,
          con tono cercano y natural. Redacta un breve guion hablado.
        '';
      };
    };
  };
}
