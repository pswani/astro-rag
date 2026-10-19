"""Locating the curated data (ontology, profiles) and the ephemeris files."""

from __future__ import annotations

import os
from pathlib import Path


class ResourceError(RuntimeError):
    pass


def _is_home(p: Path) -> bool:
    return (p / "ontology").is_dir() and (p / "profiles" / "calc").is_dir()


def astro_home() -> Path:
    """`ASTRO_HOME`, else the nearest parent of the working directory or of this package that
    holds `ontology/` and `profiles/calc/`."""
    env = os.environ.get("ASTRO_HOME")
    if env:
        p = Path(env).expanduser()
        if not _is_home(p):
            raise ResourceError(f"ASTRO_HOME={p} has no ontology/ and profiles/calc/")
        return p
    for start in (Path.cwd(), Path(__file__).resolve()):
        for p in (start, *start.parents):
            if _is_home(p):
                return p
    raise ResourceError("cannot find ontology/ and profiles/calc/; set ASTRO_HOME to the "
                        "astro-rag checkout")


def ephemeris_dir(home: Path | None = None) -> Path:
    env = os.environ.get("ASTRO_EPHE")
    return Path(env).expanduser() if env else (home or astro_home()) / "data" / "ephe"
