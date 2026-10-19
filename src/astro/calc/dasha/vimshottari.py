"""Vimshottari dasha (DAS-1, DAS-2, DAS-4; design §7.7, design-notes §10).

- First MD lord = lord of the Moon's nakshatra; balance = (1 − fraction traversed) × years.
- A sub-period starts with the parent's lord and lasts parent × years(sub-lord) / 120.
- Years convert to days with the profile's `year_days`, never by calendar anniversaries.
- All boundaries move together with the Moon under birth-time uncertainty; the shift for −u and
  +u is recorded on every period. A nakshatra change inside the interval changes the whole
  sequence and is reported through the `dasha_balance` fact's sensitivity.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, nakshatra_fraction, nakshatra_index
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.core.timescale import parse_utc_instant, utc_from_jd
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.model import DashaPeriod, FeatureResult
from astro.calc.sensitivity import assess

LEVELS = ("MD", "AD", "PD", "SD")
SYSTEM = "vimshottari"


def first_md(moon_lon: float, sequence: Sequence[tuple[str, float]],
             year_days: float) -> tuple[int, float, float]:
    """(index of the first MD lord, its balance in years, days the MD began before birth)."""
    n = nakshatra_index(moon_lon)
    i = n % len(sequence)
    years = sequence[i][1]
    f = nakshatra_fraction(moon_lon)
    return i, (1.0 - f) * years, f * years * year_days


def build_tree(chart_id: str, profile_id: str, birth_jd: float, moon_lon: float,
               sequence: Sequence[tuple[str, float]], year_days: float, depth: int,
               span_years: float, margins: tuple[float | None, float | None] = (None, None)
               ) -> list[DashaPeriod]:
    total = sum(y for _, y in sequence)
    i0, _balance, elapsed_days = first_md(moon_lon, sequence, year_days)
    out: list[DashaPeriod] = []
    end_target = birth_jd + span_years * year_days

    def children(parent_id: str, level: int, start: float, length_days: float,
                 lord_index: int) -> None:
        t = start
        for k in range(len(sequence)):
            j = (lord_index + k) % len(sequence)
            dur = length_days * sequence[j][1] / total
            pid = f"{parent_id}.{LEVELS[level]}{k + 1}"
            end = start + length_days if k == len(sequence) - 1 else t + dur
            out.append(_period(pid, level, sequence[j][0], t, end, parent_id, k, profile_id,
                               margins))
            if level + 1 < depth:
                children(pid, level + 1, t, end - t, j)
            t = end

    t = birth_jd - elapsed_days
    k = 0
    while t < end_target:
        j = (i0 + k) % len(sequence)
        dur = sequence[j][1] * year_days
        pid = f"{chart_id}/dasha/{SYSTEM}/MD{k + 1}"
        out.append(_period(pid, 0, sequence[j][0], t, t + dur, None, k, profile_id, margins))
        if depth > 1:
            children(pid, 1, t, dur, j)
        t += dur
        k += 1
    return out


def _period(pid: str, level: int, lord: str, start: float, end: float, parent: str | None,
            seq: int, profile_id: str, margins: tuple[float | None, float | None]
            ) -> DashaPeriod:
    return DashaPeriod(id=pid, system=SYSTEM, level=LEVELS[level], lord=lord,  # type: ignore
                       start_utc=utc_from_jd(start), end_utc=utc_from_jd(end), parent_id=parent,
                       sequence=seq, profile_id=profile_id, boundary_margin_days=margins)


# -- queries (DAS-2, DAS-4) ------------------------------------------------------------------

def active_chain(periods: Sequence[DashaPeriod], at: datetime) -> list[DashaPeriod]:
    """The MD → AD → … chain whose half-open periods contain `at`."""
    chain: list[DashaPeriod] = []
    parent: str | None = None
    for level in LEVELS:
        hit = [p for p in periods if p.level == level and p.parent_id == parent
               and p.start_utc <= at < p.end_utc]
        if not hit:
            break
        chain.append(hit[0])
        parent = hit[0].id
    return chain


def periods_in(periods: Sequence[DashaPeriod], start: datetime, end: datetime,
               levels: Sequence[str] = ("MD", "AD", "PD")) -> list[DashaPeriod]:
    """Every period at the given levels that overlaps the half-open window [start, end)."""
    if not start < end:
        raise ValueError("empty window")
    return sorted((p for p in periods if p.level in levels
                   and p.start_utc < end and start < p.end_utc),
                  key=lambda p: (p.start_utc, LEVELS.index(p.level)))


def sandhi(periods: Sequence[DashaPeriod], at: datetime,
           margin_days: dict[str, float]) -> dict[str, tuple[datetime, float] | None]:
    """Per level, the nearest boundary within the margin of `at` and its distance in days."""
    out: dict[str, tuple[datetime, float] | None] = {}
    for level, margin in margin_days.items():
        bounds = sorted({p.start_utc for p in periods if p.level == level}
                        | {p.end_utc for p in periods if p.level == level})
        if not bounds:
            out[level] = None
            continue
        i = bisect_right(bounds, at)
        near = bounds[max(0, i - 1):i + 1]
        best = min(near, key=lambda bd: abs((bd - at).total_seconds()))
        dist = abs((best - at).total_seconds()) / 86400.0
        out[level] = (best, dist) if dist <= margin else None
    return out


# -- features -------------------------------------------------------------------------------

class Vimshottari:
    id = "vimshottari"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        prof = ctx.profile
        levels = prof.dasha.levels
        try:
            depth = int(params.get("depth", len(levels)))
        except (TypeError, ValueError) as e:
            raise CalcError(Reason.UNSUPPORTED_FEATURE, f"depth {params['depth']!r}") from e
        if not 1 <= depth <= len(levels):  # SD only when the profile lists it
            raise CalcError(Reason.UNSUPPORTED_FEATURE,
                            f"depth {depth} outside the profile levels {levels}")
        seq = ctx.refdata.dasha_sequence(SYSTEM)
        yd = prof.dasha.year_days
        b = ctx.birth
        moon = deps.get_one("positions").fact("longitude", "graha:moon")
        moon_lon = float(moon.value)
        _, balance, elapsed = first_md(moon_lon, seq, yd)
        margins: tuple[float | None, float | None] = (None, None)
        moon_fn = ctx.lon_fn("moon")
        if b.u_days > 0:
            same = [nakshatra_index(moon_fn(b.jd_ut + s * b.u_days)) == nakshatra_index(moon_lon)
                    for s in (-1, 1)]
            shifts: list[float | None] = []
            for s, ok in zip((-1, 1), same, strict=True):
                if not ok:
                    shifts.append(None)
                    continue
                t2 = b.jd_ut + s * b.u_days
                _, _, el2 = first_md(moon_fn(t2), seq, yd)
                shifts.append((t2 - el2) - (b.jd_ut - elapsed))
            margins = (shifts[0], shifts[1])
        periods = build_tree(ctx.chart_id, prof.id, b.jd_ut, moon_lon, seq, yd, depth,
                             prof.dasha.span_years, margins)
        a = assess(moon_fn, b.jd_ut, b.u_days, width=NAKSHATRA_SPAN, step=ctx.step_days("moon"))
        fact = ctx.fact("dasha_balance", f"dasha:{SYSTEM}", balance, unit="years",
                        sensitivity=a.sensitivity, margins=a.margins)
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=(fact,),
                             periods=tuple(periods),
                             provenance={"year_days": yd, "depth": depth})


class DashaActive:
    """Active chain at an as-of instant plus sandhi flags (DAS-2, DAS-4)."""

    id = "dasha_active"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        # no depth: the tree uses the profile's levels and is shared with plain requests
        if "depth" in params:
            return [FeatureRequest.of("vimshottari", depth=params["depth"])]
        return [FeatureRequest.of("vimshottari")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        tree = deps.get_one("vimshottari")
        if "as_of" not in params:
            raise CalcError(Reason.MISSING_INPUT, "dasha_active needs as_of")
        at = utc_from_jd(parse_utc_instant(params["as_of"]))
        chain = active_chain(tree.periods, at)
        if not chain:
            raise CalcError(Reason.OUT_OF_RANGE, "as-of date outside the computed dasha span")
        levels_in_tree = {p.level for p in tree.periods}
        flags = sandhi(tree.periods, at, ctx.profile.dasha.sandhi_margin_days)
        facts = []
        for level, hit in flags.items():
            subj = f"dasha:{SYSTEM}:{level}"
            if level not in levels_in_tree:  # not computed: unknown, never a silent False
                facts.append(ctx.unknown("dasha_sandhi", subj))
                continue
            f = ctx.fact("dasha_sandhi", subj, hit is not None)
            if hit is not None:
                f = f.model_copy(update={"provenance": {"boundary_utc": hit[0].isoformat(),
                                                        "distance_days": hit[1]}})
            facts.append(f)
        return FeatureResult(feature_id=self.id, status=Status.OK, periods=tuple(chain),
                             facts=tuple(facts), provenance={"as_of": at.isoformat()})
