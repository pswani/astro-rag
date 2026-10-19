"""Download the Swiss Ephemeris files named in a calculation profile into data/ephe/.

Each file is checked against the SHA-256 pinned in the profile (design §7.1). Existing files
with the right hash are left alone. Usage: python scripts/fetch_ephemeris.py [profile.yaml ...]
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"
DEST = ROOT / "data" / "ephe"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files(profile_paths: list[Path]) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in profile_paths:
        data = YAML(typ="safe").load(p.read_text())
        for f in data["ephemeris"]["files"]:
            files[f["name"]] = f["sha256"]
    return files


def main(argv: list[str]) -> int:
    profiles = [Path(a) for a in argv] or sorted((ROOT / "profiles" / "calc").glob("*.yaml"))
    DEST.mkdir(parents=True, exist_ok=True)
    for name, digest in sorted(pinned_files(profiles).items()):
        target = DEST / name
        if target.exists() and sha256(target) == digest:
            print(f"ok       {name}")
            continue
        print(f"download {name}")
        with urllib.request.urlopen(BASE_URL + name, timeout=60) as resp:  # noqa: S310
            data = resp.read()
        if hashlib.sha256(data).hexdigest() != digest:
            print(f"SHA-256 mismatch for {name}", file=sys.stderr)
            return 1
        target.write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
