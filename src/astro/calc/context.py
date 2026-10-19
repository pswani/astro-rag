"""What a feature computes against: the normalized birth, profile, ephemeris and reference data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from astro.calc.core.timescale import MINUTE
from astro.calc.ephemeris.port import Body, Ephemeris
from astro.calc.model import ChartFact, FactValue, Sensitivity, fact_id
from astro.calc.profile import CalcProfile
from astro.calc.refdata import ReferenceData


@dataclass(frozen=True)
class NormalizedBirth:
    """The immutable, normalized input a chart is computed from (design §6.2.6)."""

    jd_ut: float                 # the birth instant; local noon when the time is unknown
    latitude: float
    longitude: float
    elevation_m: float = 0.0
    time_known: bool = True
    uncertainty_minutes: float = 0.0  # half-width u of [t − u, t + u] (design §6.3)

    @property
    def u_days(self) -> float:
        return self.uncertainty_minutes * MINUTE


@dataclass
class ChartContext:
    chart_id: str
    birth: NormalizedBirth
    profile: CalcProfile
    ephemeris: Ephemeris
    refdata: ReferenceData
    method_inputs: dict[str, Any] = field(default_factory=dict)
    # per-chart scratch space for values shared by features (e.g. sign-change instants)
    memo: dict[Any, Any] = field(default_factory=dict, repr=False, compare=False)

    # -- callables for the solver -----------------------------------------------------------
    def lon_fn(self, body: Body) -> Callable[[float], float]:
        return lambda t: self.ephemeris.body(body, t, self.profile).longitude

    def speed_fn(self, body: Body) -> Callable[[float], float]:
        return lambda t: self.ephemeris.body(body, t, self.profile).speed

    def lagna_fn(self) -> Callable[[float], float]:
        b = self.birth
        return lambda t: self.ephemeris.ascendant(t, b.latitude, b.longitude, self.profile)

    def step_days(self, key: str) -> float:
        """Sampling step for `key` (a body, `true_node` or `lagna`), from the profile."""
        steps = self.profile.sensitivity.step_minutes
        if key in ("rahu", "ketu"):
            key = "mean_node" if self.profile.nodes.model == "mean" else "true_node"
        return steps[key] * MINUTE

    def needs_speed(self, body: str) -> bool:
        """Bodies that can turn: planets and the true node. Sun, Moon and mean node cannot."""
        if body in ("sun", "moon"):
            return False
        if body in ("rahu", "ketu"):
            return self.profile.nodes.model == "true"
        return True

    # -- fact construction ------------------------------------------------------------------
    def fact(self, kind: str, subject: str, value: FactValue, *, frame: str | None = None,
             varga: str = "D1", unit: str | None = None, sensitivity: Sensitivity = "stable",
             margins: tuple[float | None, float | None] = (None, None)) -> ChartFact:
        return ChartFact(
            id=fact_id(self.chart_id, kind, subject, frame, None if varga == "D1" else varga),
            kind=kind, subject=subject, value=value, unit=unit, frame=frame, varga=varga,
            profile_id=self.profile.id, sensitivity=sensitivity, margin_minutes=margins,
        )

    def unknown(self, kind: str, subject: str, *, frame: str | None = None,
                varga: str = "D1") -> ChartFact:
        return self.fact(kind, subject, None, frame=frame, varga=varga, sensitivity="unknown")
