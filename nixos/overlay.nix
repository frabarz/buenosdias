final: prev:

let
  inherit (prev.lib) fileset;
  inherit (prev) home-assistant;

  src = fileset.toSource {
    root = ../.;
    fileset = fileset.unions [
      ../custom_components
      ../tests
      ../pyproject.toml
    ];
  };
in
{
  home-assistant-custom-components = (prev.home-assistant-custom-components or { }) // {
    buenosdias = prev.buildHomeAssistantComponent rec {
      owner = "buenosdias";
      domain = "buenosdias";
      version = "0.1.0";
      inherit src;

      dependencies = with home-assistant.python3Packages; [
        feedparser
        httpx
      ];

      nativeCheckInputs =
        with home-assistant.python3Packages;
        [
          pytestCheckHook
          pytest-homeassistant-custom-component
        ]
        ++ (home-assistant.getPackages "switch" home-assistant.python3Packages)
        ++ (home-assistant.getPackages "sensor" home-assistant.python3Packages);

      # El harness de HA registra fixtures async autouse; los tests de este
      # componente son síncronos y usan asyncio.run(), así que se necesita
      # el modo auto de pytest-asyncio.
      pytestFlags = [ "--asyncio-mode=auto" ];

      meta = {
        description = "Radio matutina personalizada para Home Assistant con LLM";
        license = prev.lib.licenses.asl20;
      };
    };
  };
}
