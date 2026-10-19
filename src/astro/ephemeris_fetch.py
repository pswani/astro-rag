"""Download the Swiss Ephemeris files named in the calculation profiles (design §7.1).

Each file is checked against the SHA-256 pinned in its profile; files already present with the
right hash are left alone.
"""

from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path

from ruamel.yaml import YAML

BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files(profile_paths: Iterable[Path]) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in profile_paths:
        data = YAML(typ="safe").load(Path(p).read_text())
        for f in data["ephemeris"]["files"]:
            files[f["name"]] = f["sha256"]
    return files


def fetch(profile_paths: Iterable[Path], dest: Path,
          log: Callable[[str], None] = print) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, digest in sorted(pinned_files(profile_paths).items()):
        target = dest / name
        if target.exists() and sha256(target) == digest:
            log(f"ok       {name}")
            continue
        log(f"download {name}")
        try:
            with urllib.request.urlopen(BASE_URL + name, timeout=60) as resp:  # noqa: S310
                data = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log(f"failed   {name}: {e}")
            ok = False
            continue
        if hashlib.sha256(data).hexdigest() != digest:
            log(f"SHA-256 mismatch for {name}; not written")
            ok = False
            continue
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)  # never leave a truncated file under the real name
    return ok
