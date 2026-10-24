#!/usr/bin/env python3
"""Install the pinned Linux solc for Docker and verify vendored OpenZeppelin files."""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Verify only; never download")
    args = parser.parse_args()
    vendor = ROOT / "vendor/openzeppelin"
    source = json.loads((vendor / "SOURCES.json").read_text(encoding="utf-8"))
    for name, expected in source["files"].items():
        path = vendor / name
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            raise SystemExit(f"OpenZeppelin source missing or modified: {name}")
    compiler = json.loads((ROOT / "solc.lock.json").read_text(encoding="utf-8"))
    target = ROOT / ".toolchain/solc-0.8.30"
    if not target.is_file():
        if args.offline:
            raise SystemExit("Pinned solc absent; run prepare.py during installation")
        with urllib.request.urlopen(compiler["url"], timeout=60) as response:
            data = response.read()
        if sha256(data) != compiler["sha256"]:
            raise SystemExit("Downloaded solc SHA-256 mismatch")
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
    if sha256(target.read_bytes()) != compiler["sha256"]:
        raise SystemExit("Installed solc SHA-256 mismatch")
    target.chmod(0o755)
    print(json.dumps({"openzeppelin_files_verified": len(source["files"]), "revision": source["git_revision"],
                      "solc": compiler["long_version"], "solc_sha256": compiler["sha256"], "offline": args.offline}))


if __name__ == "__main__":
    main()
