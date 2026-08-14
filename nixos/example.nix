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

    # NOTE (v0.2.0): the integration is configured through the HA UI config
    # flow (Settings → Devices & Services → Add Integration → "Buenos Días");
    # the API key goes into the entry data, not secrets.yaml.
    #
    # The `buenosdias:` YAML block below is a one-time migration shim: it just
    # imports the settings into a config entry at startup and is ignored once
    # an entry exists. New installations should omit it entirely and set
    # everything up in the UI. Keep secrets via `!secret` if you do migrate.
    config = {
      # Base HA configuration — note: no `buenosdias` block at all.
      default_config = { };

      # OPTIONAL one-time migration: set the integration up in the UI and
      # skip this. Only present to import pre-v0.2.0 YAML settings into a
      # config entry on first startup:
      #
      #   buenosdias = {
      #     llm = {
      #       mode = "ha_conversation";
      #       # agent = "conversation.assist";
      #       max_chars = 2000;
      #       openai = {
      #         base_url = "http://localhost:11434/v1";
      #         api_key = "!secret buenosdias_llm_api_key";
      #         model = "llama3";
      #       };
      #     };
      #     tts = {
      #       entity_id = "tts.piper";
      #       media_player = "media_player.sala";
      #       language = "es-ES";
      #       volume = 0.6;
      #       restore_volume = true;
      #     };
      #     sources = {
      #       weather = [ "weather.casa" ];
      #       calendar = [ "calendar.familia" ];
      #       sensors = [ "sensor.consumo_diario" ];
      #       rss.feeds = [ ];
      #     };
      #     schedule = {
      #       time = "07:00";
      #       skip_days = [ "sat" "sun" ];
      #       feriados = [ "2026-01-01" ];
      #       skip_if_emitted = true;
      #     };
      #     persona = ''
      #       You are the host of a morning radio show. Speak in a warm,
      #       natural tone and write a short spoken script.
      #     '';
      #   };
    };
  };
}
