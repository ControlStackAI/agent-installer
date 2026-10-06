{ pkgs }:
let
  input = builtins.fromJSON (builtins.readFile ./inputs.lock.json);
  archive = pkgs.fetchurl {
    inherit (input.package) url sha256;
  };
in pkgs.runCommand "codex-cli-${input.version}" {
  nativeBuildInputs = [ pkgs.gnutar pkgs.gzip ];
  meta = {
    description = "Official pinned Codex Linux musl bundle";
    license = pkgs.lib.licenses.asl20;
    platforms = [ "x86_64-linux" ];
  };
} ''
  mkdir -p $out/opt/codex $out/bin
  tar -xzf ${archive} -C $out/opt/codex --no-same-owner
  ln -s $out/opt/codex/bin/codex $out/bin/codex
  ln -s $out/opt/codex/bin/codex-code-mode-host $out/bin/codex-code-mode-host
  $out/bin/codex --version | grep -Fx 'codex-cli ${input.version}'
''
