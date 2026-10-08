{ pkgs }:
pkgs.rustPlatform.buildRustPackage {
  pname = "agent-installer-tui";
  version = "0.1.0";
  src = pkgs.lib.fileset.toSource {
    root = ./.;
    fileset = pkgs.lib.fileset.unions [ ./Cargo.toml ./Cargo.lock ./src ];
  };
  cargoLock.lockFile = ./Cargo.lock;
  nativeBuildInputs = [ pkgs.python3 ];
  postInstall = ''
    python3 ${../../scripts/tui-notices.py} --lock ${./Cargo.lock} \
      --sources "$cargoDeps" --output "$out/share/agent-installer-tui/notices"
  '';
  doCheck = true;
  meta = {
    description = "Optional Ratatui guided console for Agent Installer";
    license = pkgs.lib.licenses.asl20;
    mainProgram = "agent-installer-tui";
    platforms = pkgs.lib.platforms.linux;
  };
}
