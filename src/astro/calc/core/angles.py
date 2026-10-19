"""Angle arithmetic and zodiac indexing.

All longitudes are degrees. Indices are 0-based; ontology IDs carry the names.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

SIGN_SPAN = 30.0
NAKSHATRA_SPAN = 40.0 / 3.0  # 13°20′
PADA_SPAN = 10.0 / 3.0  # 3°20′


def norm360(x: float) -> float:
    """Normalize to [0, 360)."""
    r = math.fmod(x, 360.0)
    if r < 0:
        r += 360.0
    # fmod of a tiny negative number can round to exactly 360.0
    return 0.0 if r >= 360.0 else r


def signed_diff(a: float, b: float) -> float:
    """Shortest signed angle a − b, in (−180, 180]."""
    d = norm360(a - b)
    return d - 360.0 if d > 180.0 else d


def unwrap(values: Sequence[float]) -> list[float]:
    """Remove 360° jumps so consecutive values differ by less than 180°."""
    out: list[float] = []
    for v in values:
        if not out:
            out.append(v)
        else:
            out.append(out[-1] + signed_diff(v, out[-1]))
    return out


def sign_index(lon: float) -> int:
    """0 = Aries … 11 = Pisces."""
    return min(int(norm360(lon) // SIGN_SPAN), 11)


def deg_in_sign(lon: float) -> float:
    return norm360(lon) - sign_index(lon) * SIGN_SPAN


# Spans of 40/3° and 10/3° are not exact in binary, so indices scale by 3 first: a longitude that
# is exactly on a boundary (e.g. 30°) then lands in the later sector, as it must.


def pada_count(lon: float) -> int:
    """Padas completed since 0° Aries: 0…107."""
    return min(int(norm360(lon) * 3.0 // 10.0), 107)


def nakshatra_index(lon: float) -> int:
    """0 = Ashwini … 26 = Revati."""
    return min(int(norm360(lon) * 3.0 // 40.0), 26)


def nakshatra_fraction(lon: float) -> float:
    """Fraction of the current nakshatra already traversed, in [0, 1)."""
    f = (norm360(lon) * 3.0 - nakshatra_index(lon) * 40.0) / 40.0
    return min(max(f, 0.0), math.nextafter(1.0, 0.0))


def pada(lon: float) -> int:
    """1…4 within the nakshatra."""
    return pada_count(lon) % 4 + 1


def houses_apart(from_sign: int, to_sign: int) -> int:
    """Inclusive house count from one sign to another: same sign = 1, next sign = 2."""
    return (to_sign - from_sign) % 12 + 1


def is_odd_sign(sign: int) -> bool:
    """Aries, Gemini, Leo… are odd (index 0, 2, 4…)."""
    return sign % 2 == 0


def modality(sign: int) -> str:
    """movable (chara), fixed (sthira) or dual (dvisvabhava)."""
    return ("movable", "fixed", "dual")[sign % 3]


def to_dms(lon: float) -> str:
    """Degrees within sign as D°MM′SS″ (for display and fixtures)."""
    total = round(deg_in_sign(lon) * 3600)
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{d:02d}°{m:02d}′{s:02d}″"
