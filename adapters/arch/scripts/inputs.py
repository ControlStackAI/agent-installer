#!/usr/bin/env python3
"""Resolve explicit upstream inputs; building never implicitly updates them."""
import argparse
import datetime as dt
import hashlib
import io
import json
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCH_SIGNER = "3E80CA1A8B89F69CBA57D98A76A5EF9054449A5C"
ZFS_SIGNER = "3A9917BF0DED5C13F69AC68FABEC0A1208037BE9"
BUILDER = "archlinux@sha256:4e77cf2ea5f410e6f8be5abf93ccf17ce2436e87a138c167208356711a405dbd"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ControlStackAI-agent-installer"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def release(repo, tag):
    suffix = "latest" if tag == "latest" else "tags/" + tag
    return json.loads(fetch(f"https://api.github.com/repos/{repo}/releases/{suffix}"))


def asset(data, name):
    matches = [a for a in data["assets"] if a["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Required released asset unavailable: {name}")
    a = matches[0]
    digest = a.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError(f"Upstream SHA256 missing for {name}; review manually")
    return {"name": name, "url": a["browser_download_url"], "sha256": digest[7:]}


def kernel_from_db(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        for member in archive.getmembers():
            if re.fullmatch(r"linux-[^/]+/desc", member.name):
                description = archive.extractfile(member).read().decode()
                fields = description.strip().split("\n\n")
                return {f.splitlines()[0].strip("%"): f.splitlines()[1] for f in fields}
    raise ValueError("linux package missing from frozen core database")


def validate(lock):
    if lock["schema"] != 1:
        raise ValueError("Unsupported input schema")
    arch = lock["arch"]
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", arch["snapshot"]):
        raise ValueError("Invalid Arch snapshot")
    version = arch["kernel_package_version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+\.arch\d+-\d+", version):
        raise ValueError("Unsupported linux package version format")
    if arch["kernel_release"] != version.replace(".arch", "-arch"):
        raise ValueError("Kernel release does not match package")
    policy = json.loads((ROOT / "config/zfs-policy.json").read_text())
    approved = policy[lock["zfs"]["version"]]
    major_minor = tuple(map(int, version.split(".")[:2]))
    if not tuple(map(int, approved["minimum_linux"].split("."))) <= major_minor <= tuple(map(int, approved["maximum_linux"].split("."))):
        raise ValueError("Kernel outside reviewed released OpenZFS support")
    kernel_asset = rf'zfs-linux-{re.escape(lock["zfs"]["version"])}_{re.escape(version.replace("-", "."))}-\d+-x86_64.pkg.tar.zst'
    if not re.fullmatch(kernel_asset, lock["zfs"]["packages"][0]["name"]):
        raise ValueError("ZFS module package does not match the locked kernel")
    for package in lock["zfs"]["packages"]:
        if package["signature"]["name"] != package["name"] + ".sig":
            raise ValueError("Wrong detached package signature")
    if arch["signer"] != ARCH_SIGNER or lock["zfs"]["signer"] != ZFS_SIGNER:
        raise ValueError("Signing key rotation requires review")
    downloads = [arch["iso"], arch["iso"]["signature"], lock["codex"]["package"], arch["linux"]]
    for package in lock["zfs"]["packages"]:
        downloads.extend([package, package["signature"]])
    for item in downloads:
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", item["name"]):
            raise ValueError("Unsafe download filename")
        if not item["url"].startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("HTTPS and SHA256 required")
    if not re.fullmatch(r"archlinux@sha256:[0-9a-f]{64}", lock["builder_image"]):
        raise ValueError("Builder image must be pinned")


def resolve(arch_version="latest", codex_version="latest", snapshot=None):
    snapshot = snapshot or dt.datetime.now(dt.timezone.utc).strftime("%Y/%m/%d")
    iso_base = "https://geo.mirror.pkgbuild.com/iso/" + arch_version + "/"
    sums = fetch(iso_base + "sha256sums.txt").decode()
    found = re.findall(r"^([0-9a-f]{64})\s+(archlinux-(\d{4}\.\d{2}\.\d{2})-x86_64\.iso)$", sums, re.M)
    if len(found) != 1:
        raise ValueError("Cannot resolve official x86_64 Arch ISO")
    sha, name, version = found[0]
    iso_url = f"https://archive.archlinux.org/iso/{version}/{name}"
    sig_url = iso_url + ".sig"
    iso = {"name": name, "url": iso_url, "sha256": sha,
           "signature": {"name": name + ".sig", "url": sig_url, "sha256": hashlib.sha256(fetch(sig_url)).hexdigest()}}
    db_base = f"https://archive.archlinux.org/repos/{snapshot}/core/os/x86_64/"
    kernel = kernel_from_db(fetch(db_base + "core.db"))
    codex = release("openai/codex", "latest" if codex_version == "latest" else "rust-v" + codex_version.removeprefix("rust-v"))
    zfs = release("archzfs/archzfs", "experimental")
    kversion = kernel["VERSION"]
    pattern = rf"zfs-linux-(\d+\.\d+\.\d+)_{re.escape(kversion.replace('-', '.'))}-\d+-x86_64.pkg.tar.zst"
    matches = [a for a in zfs["assets"] if re.fullmatch(pattern, a["name"])]
    if len(matches) != 1:
        raise ValueError(f"No signed prebuilt ZFS module for latest snapshot kernel {kversion}; keep previous inputs or choose a supported snapshot")
    zversion = re.fullmatch(pattern, matches[0]["name"])[1]
    utils = [a["name"] for a in zfs["assets"] if re.fullmatch(rf"zfs-utils-{re.escape(zversion)}-\d+-x86_64.pkg.tar.zst", a["name"])]
    if len(utils) != 1:
        raise ValueError("ZFS utility release unavailable")
    packages = []
    for pname in [matches[0]["name"], utils[0]]:
        package = asset(zfs, pname)
        package["signature"] = asset(zfs, pname + ".sig")
        packages.append(package)
    lock = {"schema": 1, "builder_image": BUILDER,
            "arch": {"version": version, "snapshot": snapshot, "signer": ARCH_SIGNER, "iso": iso,
                     "kernel_package_version": kversion, "kernel_release": kversion.replace(".arch", "-arch"),
                     "linux": {"name": kernel["FILENAME"], "url": db_base + kernel["FILENAME"], "sha256": kernel["SHA256SUM"]}},
            "codex": {"version": codex["tag_name"].removeprefix("rust-v"), "package": asset(codex, "codex-package-x86_64-unknown-linux-musl.tar.gz")},
            "zfs": {"version": zversion, "signer": ZFS_SIGNER, "packages": packages}}
    validate(lock)
    return lock


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch-version", default="latest")
    parser.add_argument("--codex-version", default="latest")
    parser.add_argument("--snapshot", help="Frozen Arch repository date YYYY/MM/DD (default UTC today)")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "inputs.lock.json"
    if args.check:
        validate(json.loads(path.read_text()))
        print("Input lock valid")
    else:
        lock = resolve(args.arch_version, args.codex_version, args.snapshot)
        path.write_text(json.dumps(lock, indent=2) + "\n")
        print(f'Pinned Arch {lock["arch"]["version"]}, Linux {lock["arch"]["kernel_release"]}, ZFS {lock["zfs"]["version"]}, Codex {lock["codex"]["version"]}')
