"""Bounded Linux/Docker preprocessing for this project's local OSM extract."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

IMAGE = ("ghcr.io/project-osrm/osrm-backend"
         "@sha256:60a43e45aa42226e76b359ca7308e49be1a41af096bf7b6c9c2a471f0e856078")


def check_space(path):
    usage = shutil.disk_usage(path)
    if usage.used / usage.total >= 0.8 or usage.free < 3 * 1024 ** 3:
        raise RuntimeError(f"disk gate failed for {path}; need <80% used and 3GiB free")
    return {"path": str(path), "total": usage.total, "used": usage.used, "free": usage.free}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve(strict=True)
    source = directory / "nanan.osm"
    if not source.is_file() or source.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("expected a bounded nanan.osm extract")
    if (directory / "build-complete.json").exists():
        raise ValueError("build already completed; inspect it before rebuilding")
    baseline = [check_space(p) for p in ("/", "/var/lib/docker", directory)]
    manifest = subprocess.run(["docker", "manifest", "inspect", IMAGE], check=True,
                              capture_output=True, text=True, timeout=60)
    metadata = json.loads(manifest.stdout)
    (directory / "image-index.json").write_text(manifest.stdout, encoding="utf-8")
    if "manifests" in metadata:
        selected = [entry for entry in metadata["manifests"]
                    if entry.get("platform") == {"architecture": "amd64", "os": "linux"}]
        if len(selected) != 1:
            raise RuntimeError("exactly one linux/amd64 image manifest required")
        platform_ref = IMAGE.split("@")[0] + "@" + selected[0]["digest"]
        manifest = subprocess.run(["docker", "manifest", "inspect", platform_ref], check=True,
                                  capture_output=True, text=True, timeout=60)
        metadata = json.loads(manifest.stdout)
    (directory / "image-manifest.json").write_text(manifest.stdout, encoding="utf-8")
    compressed_bytes = sum(layer["size"] for layer in metadata.get("layers", []))
    if not 0 < compressed_bytes <= 300 * 1024 * 1024:
        raise RuntimeError("image size not verified within 300MiB compressed budget")
    subprocess.run(["docker", "pull", IMAGE], check=True, timeout=180)
    check_space("/var/lib/docker")
    common = ["docker", "run", "--rm", "--network", "none", "--cpus", "2",
              "--memory", "2g", "--user", f"{os.getuid()}:{os.getgid()}",
              "-v", f"{directory}:/data", IMAGE]
    commands = [
        ["osrm-extract", "-t", "2", "-p", "/opt/car.lua", "/data/nanan.osm"],
        ["osrm-partition", "-t", "2", "/data/nanan.osrm"],
        ["osrm-customize", "-t", "2", "/data/nanan.osrm"],
    ]
    for command in commands:
        check_space(directory)
        with (directory / f"{command[0]}.log").open("w") as log:
            subprocess.run(common + command, check=True, stdout=log, stderr=subprocess.STDOUT,
                           timeout=180)
    result = {"image": IMAGE, "compressed_bytes": compressed_bytes,
              "release": "26.10.0-amd64-debian",
              "osm_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "created_at": datetime.now(timezone.utc).isoformat(), "disk_before": baseline,
              "disk_after": [check_space(p) for p in ("/", "/var/lib/docker", directory)],
              "commands": commands, "files": sorted(p.name for p in directory.glob("nanan.osrm*"))}
    (directory / "build-complete.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
