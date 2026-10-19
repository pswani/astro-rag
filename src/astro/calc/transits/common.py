"""Shared helpers for transit features."""

from __future__ import annotations

from astro.calc.core.status import CalcError, Reason
from astro.calc.core.timescale import parse_utc_instant as parse_instant

__all__ = ["check_window", "parse_instant", "window"]

SLOW_WINDOW_DAYS = 5 * 365.25   # design §7.8 window limits
MOON_WINDOW_DAYS = 1 * 365.25


def window(params: dict) -> tuple[float, float]:
    try:
        start, end = parse_instant(params["start"]), parse_instant(params["end"])
    except KeyError as e:
        raise CalcError(Reason.MISSING_INPUT, f"window needs {e.args[0]!r}") from e
    if not start < end:
        raise CalcError(Reason.UNSUPPORTED_WINDOW, "window start must precede its end")
    return start, end


def check_window(start: float, end: float, bodies: tuple[str, ...]) -> None:
    limit = MOON_WINDOW_DAYS if "moon" in bodies else SLOW_WINDOW_DAYS
    if end - start > limit:
        raise CalcError(Reason.UNSUPPORTED_WINDOW,
                        f"window of {end - start:.0f} days exceeds {limit:.0f} for {bodies}")
