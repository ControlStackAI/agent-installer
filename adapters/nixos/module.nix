# Reusable onboarding module; live-only configuration is in live-image.nix.
{ lib, pkgs, config, ... }:
let
  cfg = config.services.controlstackInstaller;
  core = import ./package.nix { inherit pkgs; };
  codex = import ../../runtimes/codex/package.nix { inherit pkgs; };
in {
  options.services.controlstackInstaller.enable = lib.mkEnableOption "ControlStackAI installer tools";
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ core codex pkgs.curl pkgs.git pkgs.python3 pkgs.tmux ];
    environment.etc."agent-installer/image.json".text = builtins.toJSON {
      schema = 1; distro = "nixos"; runtime = "codex";
    };
    # Canonical paths let all runtimes and distro adapters share the same core.
    systemd.tmpfiles.rules = [
      "L+ /usr/share/agent-installer - - - - ${core}/share/agent-installer"
    ];
    networking.networkmanager.enable = true;
    networking.wireless.enable = lib.mkForce false;
    services.timesyncd.enable = true;
  };
}
