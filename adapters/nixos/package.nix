{ pkgs }:
let
  source = pkgs.lib.fileset.toSource {
    root = ../..;
    fileset = pkgs.lib.fileset.unions [ ../../core ../../identity ../../profiles ../../presets ../../runtimes ../../tests ];
  };
in pkgs.runCommand "controlstack-installer-core" {
  nativeBuildInputs = [ pkgs.makeWrapper ];
} ''
  mkdir -p $out/lib/agent-installer $out/bin $out/share/agent-installer
  cp -r ${source}/core $out/lib/agent-installer/core
  mkdir -p $out/lib/agent-installer/runtimes/codex
  cp ${source}/runtimes/__init__.py $out/lib/agent-installer/runtimes/
  cp ${source}/runtimes/codex/*.py $out/lib/agent-installer/runtimes/codex/
  cp -r ${source}/identity ${source}/profiles ${source}/presets ${source}/tests $out/share/agent-installer/
  mkdir -p $out/share/agent-installer/runtimes
  cp ${source}/runtimes/codex/manifest.json $out/share/agent-installer/runtimes/codex.json
  makeWrapper ${pkgs.python3}/bin/python3 $out/bin/agent-installer \
    --set PYTHONPATH $out/lib/agent-installer --add-flags "-m core.launcher"
  makeWrapper $out/bin/agent-installer $out/bin/agent-preflight --add-flags --preflight
  makeWrapper $out/bin/agent-installer $out/bin/agent-network --add-flags --network
  makeWrapper ${pkgs.python3}/bin/python3 $out/bin/agent-support \
    --set PYTHONPATH $out/lib/agent-installer --add-flags "-m core.assistant" \
    --add-flags "--share $out/share/agent-installer" \
    --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.pciutils pkgs.util-linux pkgs.iproute2 pkgs.procps pkgs.kmod pkgs.systemd pkgs.curl ]}
''
