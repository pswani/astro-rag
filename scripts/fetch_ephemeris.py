"""Download the Swiss Ephemeris files pinned in the calculation profiles into data/ephe/.

Usage: python scripts/fetch_ephemeris.py [profile.yaml ...]   (same as `astro ephemeris fetch`)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astro.ephemeris_fetch import fetch  # noqa: E402


def main(argv: list[str]) -> int:
    profiles = [Path(a) for a in argv] or sorted((ROOT / "profiles" / "calc").glob("*.yaml"))
    return 0 if fetch(profiles, ROOT / "data" / "ephe") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
