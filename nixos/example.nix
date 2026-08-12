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
    # You can add more components, e.g. [ "frigate" "buenosdias" ].
    customComponents = [ pkgs.home-assistant-custom-components.buenosdias ];

    config = {
      # Base HA configuration.
      default_config = { };

      # Configuration block of the buenosdias integration.
      # Secrets (api_key) only via !secret, see config.example.yaml.
      buenosdias = {
        llm = {
          mode = "ha_conversation";
          # agent = "conversation.assist";   # optional
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
              url = "https://www.example.org/news/rss.xml";
              kind = "news";
              max_age_hours = 24;
              max_items = 5;
            }
          ];
        };

        schedule = {
          time = "07:00";
          # time_entity = "sensor.phone_alarm";   # dynamic time from an entity
          skip_days = [
            "sat"
            "sun"
          ];
          feriados = [ "2026-01-01" ];
          skip_if_emitted = true;
        };

        # The persona controls the script's language and style. Write it in
        # the language you want the script spoken in (e.g. Spanish).
        persona = ''
          You are the host of a morning radio show. Speak in a warm, natural
          tone and write a short spoken script.
        '';
      };
    };
  };
}
