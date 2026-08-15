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
      version = "0.3.1";
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

      # The HA harness registers autouse async fixtures; this component's
      # tests are synchronous and use asyncio.run(), so pytest-asyncio's
      # auto mode is required.
      pytestFlags = [ "--asyncio-mode=auto" ];

      meta = {
        description = "A personalized morning radio for Home Assistant";
        license = prev.lib.licenses.asl20;
      };
    };
  };
}
