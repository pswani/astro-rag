"""Half-open intervals [start, end) and window segmentation (design §7.4, §10.5)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class _Ordered(Protocol):
    def __lt__(self, other: object, /) -> bool: ...
    def __le__(self, other: object, /) -> bool: ...


T = TypeVar("T", bound=_Ordered)


@dataclass(frozen=True, order=True)
class Interval(Generic[T]):
    start: T
    end: T

    def __post_init__(self) -> None:
        if not self.start < self.end:
            raise ValueError(f"empty or inverted interval [{self.start}, {self.end})")

    def contains(self, t: T) -> bool:
        return self.start <= t and t < self.end

    def overlaps(self, other: Interval[T]) -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: Interval[T]) -> Interval[T] | None:
        lo = max(self.start, other.start)
        hi = min(self.end, other.end)
        return Interval(lo, hi) if lo < hi else None


def segment(window: Interval[T], boundaries: Iterable[T]) -> list[Interval[T]]:
    """Cut `window` at every boundary strictly inside it; the pieces tile the window."""
    cuts = sorted({b for b in boundaries if window.start < b and b < window.end})
    edges = [window.start, *cuts, window.end]
    return [Interval(a, b) for a, b in zip(edges, edges[1:], strict=False)]
