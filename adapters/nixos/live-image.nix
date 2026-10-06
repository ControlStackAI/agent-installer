{ lib, pkgs, modulesPath, config, ... }:
{
  imports = [ (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix") ./module.nix ];
  services.controlstackInstaller.enable = true;
  services.getty.autologinUser = lib.mkForce "root";
  # Remain inside released ZFS compatibility, even when nixpkgs' latest kernel is newer.
  boot.kernelModules = [ "qemu_fw_cfg" ];
  boot.supportedFilesystems = [ "zfs" ];
  boot.kernelPackages = pkgs.linuxPackages_latest;
  boot.zfs.package = pkgs.zfs_2_4;
  assertions = [{
    assertion = !config.boot.zfs.modulePackage.meta.broken;
    message = "The pinned latest kernel is outside released ZFS support; select a reviewed supported kernel.";
  }];
  boot.zfs.forceImportRoot = false;
  networking.hostName = "agent-live";
  networking.hostId = "c057ac01"; # Live image only; target hosts require unique IDs.
  environment.etc."agent-installer/live-image".text = "nixos\n";
  environment.interactiveShellInit = builtins.readFile ../../core/live-login.sh;
  image.fileName = lib.mkForce "controlstack-agent-nixos-x86_64.iso";
  isoImage.volumeID = "AGENT_NIXOS";
  isoImage.squashfsCompression = "zstd -Xcompression-level 6";
  systemd.services.agent-smoke-test = {
    description = "Explicit disposable-VM installer qualification";
    wantedBy = [ "multi-user.target" ];
    after = [ "NetworkManager.service" "systemd-timesyncd.service" "systemd-tmpfiles-setup.service" ];
    unitConfig.ConditionPathExists = "/sys/firmware/qemu_fw_cfg/by_name/opt/org.controlstackai/smoke/raw";
    path = [ config.system.path pkgs.kmod pkgs.util-linux pkgs.systemd pkgs.gnugrep pkgs.gawk ];
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.bash}/bin/bash ${../../core/smoke.sh}";
      Environment = "PYTHONPATH=${import ./package.nix { inherit pkgs; }}/lib/agent-installer";
    };
  };
  services.openssh.enable = lib.mkForce false;
  system.stateVersion = "26.05";
}
