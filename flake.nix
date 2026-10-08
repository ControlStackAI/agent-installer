{
  description = "ControlStackAI distro-independent agent installer";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    live = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [ self.nixosModules.liveImage ];
    };
  in {
    nixosModules.default = import ./adapters/nixos/module.nix;
    nixosModules.liveImage = import ./adapters/nixos/live-image.nix;
    packages.${system} = {
      installer-core = import ./adapters/nixos/package.nix { inherit pkgs; };
      installer-tui = import ./frontends/ratatui/package.nix { inherit pkgs; };
      codex = import ./runtimes/codex/package.nix { inherit pkgs; };
      nixos-iso = live.config.system.build.isoImage;
    };
    nixosConfigurations.live = live;
  };
}
