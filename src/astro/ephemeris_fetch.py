"""Download the Swiss Ephemeris files named in the calculation profiles (design §7.1).

Each file is checked against the SHA-256 pinned in its profile; files already present with the
right hash are left alone. TLS trusts the system's certificate store plus certifi's bundle, so
Python builds that ship without root certificates (python.org installers on macOS) still verify.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path

from ruamel.yaml import YAML

BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"


def ssl_context() -> ssl.SSLContext:
    """The default context, with certifi's roots added when certifi is installed."""
    ctx = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return ctx
    ctx.load_verify_locations(cafile=certifi.where())
    return ctx


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
    ctx = ssl_context()
    for name, digest in sorted(pinned_files(profile_paths).items()):
        target = dest / name
        if target.exists() and sha256(target) == digest:
            log(f"ok       {name}")
            continue
        log(f"download {name}")
        try:
            with urllib.request.urlopen(BASE_URL + name, timeout=60,  # noqa: S310
                                        context=ctx) as resp:
                data = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log(f"failed   {name}: {e}")
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                log("         the TLS certificate could not be verified; see README "
                    "'Troubleshooting' (SSL_CERT_FILE, or 'Install Certificates.command' on macOS)")
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
