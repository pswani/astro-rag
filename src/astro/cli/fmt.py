"""Small formatting helpers shared by the CLI (kept import-light)."""

from __future__ import annotations


def format_offset(minutes: float) -> str:
    sign = "-" if minutes < 0 else "+"
    total = round(abs(minutes))
    return f"UTC{sign}{total // 60:02d}:{total % 60:02d}"
