"""File-version stamps for caches that must notice edits."""

from __future__ import annotations

from pathlib import Path


def stamp(directory: Path, pattern: str = "*.yaml") -> tuple[tuple[str, int, int], ...]:
    """(name, size, mtime_ns) of each matching file; a file removed while scanning is skipped."""
    out = []
    for p in sorted(Path(directory).glob(pattern)):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        out.append((p.name, st.st_size, st.st_mtime_ns))
    return tuple(out)


class VersionedCache:
    """One entry per key, replaced when the files' stamp changes (no unbounded growth)."""

    def __init__(self) -> None:
        self._entries: dict = {}

    def get(self, key, version, build):
        hit = self._entries.get(key)
        if hit is not None and hit[0] == version:
            return hit[1]
        value = build()
        self._entries[key] = (version, value)
        return value

    def clear(self) -> None:
        self._entries.clear()
