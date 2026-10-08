#!/usr/bin/env python3
"""Build from reviewed inputs using a disposable Docker container with mount capability."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from inputs import ROOT, validate


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def candidate_urls(item):
    url = item['url']
    prefix = 'https://archive.archlinux.org/iso/'
    if url.startswith(prefix):
        return ['https://geo.mirror.pkgbuild.com/iso/' + url[len(prefix):], url]
    if url.startswith('https://archive.archlinux.org/repos/') and '/core/os/x86_64/' in url:
        return ['https://geo.mirror.pkgbuild.com/core/os/x86_64/' + item['name'], url]
    return [url]


def download(item, cache, reuse_root=None):
    path = cache / item["name"]
    if path.exists():
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Cached input SHA256 mismatch: {path}; remove it explicitly to retry")
        return path
    if reuse_root is not None:
        # Reuse identical bytes across locks; release archives can have the same
        # filename with different contents. Every candidate must match the hash.
        candidates = [reuse_root / item['name'], *reuse_root.glob('*/' + item['name'])]
        for candidate in candidates:
            if candidate != path and candidate.is_file() and sha256(candidate) == item['sha256']:
                os.link(candidate, path)
                return path
    temporary = path.with_suffix(path.suffix + ".part")
    print(f'Downloading {item["name"]}', flush=True)
    error = None
    for url in candidate_urls(item):
        for attempt in range(3):
            request = urllib.request.Request(url, headers={"User-Agent": "ControlStackAI-agent-installer"})
            try:
                with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                error = None
                break
            except (OSError, urllib.error.URLError) as exc:
                error = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 404):
                    break
                time.sleep(2 ** attempt)
        if error is None:
            break
    if error is not None:
        raise error
    if sha256(temporary) != item["sha256"]:
        temporary.unlink()
        raise ValueError(f'Upstream input SHA256 mismatch: {item["name"]}')
    temporary.replace(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, help="Reuse a local official ISO after checking its locked SHA256")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--download-only", action="store_true", help="Fetch and verify inputs without building")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    lock = json.loads((ROOT / "inputs.lock.json").read_text())
    validate(lock)
    reuse_root = ROOT / '.build/downloads'
    lock_id = hashlib.sha256((ROOT / 'inputs.lock.json').read_bytes()).hexdigest()
    cache = reuse_root / lock_id
    cache.mkdir(parents=True, exist_ok=True)
    iso = lock["arch"]["iso"]
    if args.iso:
        if sha256(args.iso) != iso["sha256"]:
            raise ValueError("Supplied Arch ISO does not match the input lock")
        destination = cache / iso["name"]
        if not destination.exists():
            # A copy avoids granting the container access to any other host directory.
            shutil.copyfile(args.iso, destination)
    downloads = [iso, iso["signature"], lock["codex"]["package"], lock["arch"]["linux"]]
    for package in lock["zfs"]["packages"]:
        downloads.extend([package, package["signature"]])
    for item in downloads:
        download(item, cache, reuse_root)
    if args.download_only:
        return
    subprocess.run(["docker", "build", "--build-arg", "BASE_IMAGE=" + lock["builder_image"],
                    "--build-arg", "ARCH_SNAPSHOT=" + lock["arch"]["snapshot"],
                    "-t", "arch-agent-builder:" + lock["arch"]["snapshot"].replace("/", "-"),
                    "-f", str(ROOT / "build/Dockerfile"), str(ROOT / "build")], check=True)
    (ROOT / 'dist').mkdir(exist_ok=True)
    command = ["docker", "run", "--rm", "--cap-add=SYS_ADMIN", "--security-opt=apparmor=unconfined", "--network=bridge"]
    # Mount only build sources: never expose .git checkout credentials, ignored
    # auth files, or other files an operator keeps beside the source tree.
    for name in ('scripts', 'live', 'config', 'inputs.lock.json'):
        command.extend(['--mount', f'type=bind,src={ROOT / name},dst=/repo/{name},readonly'])
    for name in ('core', 'runtimes', 'identity', 'profiles', 'presets', 'tests'):
        command.extend(['--mount', f'type=bind,src={ROOT.parent.parent / name},dst=/shared/{name},readonly'])
    for name in ('.build', 'dist'):
        command.extend(['--mount', f'type=bind,src={ROOT / name},dst=/repo/{name}'])
    command.extend(["-e", "BUILD_JOBS=" + str(args.jobs),
                    "-e", "OUTPUT_UID=" + str(os.getuid()), "-e", "OUTPUT_GID=" + str(os.getgid()),
                    "arch-agent-builder:" + lock["arch"]["snapshot"].replace("/", "-"),
                    "bash", "/repo/scripts/remaster.sh"])
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
