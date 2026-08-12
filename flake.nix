{
  description = "buenosdias: a personalized morning radio for Home Assistant with LLM";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    {
      self,
      nixpkgs,
    }:
    let
      system = "x86_64-linux";
      overlay = import ./nixos/overlay.nix;
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ overlay ];
      };
      component = pkgs.home-assistant-custom-components.buenosdias;
      home-assistant = pkgs.home-assistant;
    in
    {
      overlays.default = overlay;

      nixosModules.default = {
        lib,
        pkgs,
        ...
      }: {
        nixpkgs.overlays = [ overlay ];
      };

      packages.${system} = {
        inherit component;
        default = component;
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          (
            home-assistant.python3Packages.python.buildEnv.override {
              extraLibs =
                (with home-assistant.python3Packages; [
                  pytest
                  pytest-homeassistant-custom-component
                  feedparser
                  httpx
                ])
                ++ (home-assistant.getPackages "switch" home-assistant.python3Packages)
                ++ (home-assistant.getPackages "sensor" home-assistant.python3Packages);
            }
          )
        ];
        shellHook = ''
          echo "buenosdias dev shell (Python 3.14 + Home Assistant). Run: pytest -q"
        '';
      };

      checks.${system} = {
        build = component;
      };
    };
}
