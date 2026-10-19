"""Divisional charts from the data-driven spec in `ontology/vargas.yaml` (VAR-1, G-V1).

varga_sign = (sign + start_offset(sign) + floor(deg_in_sign / (30 / N))) mod 12. For equal-part
vargas every boundary is a multiple of 30/N degrees, so sensitivity uses that width.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import deg_in_sign, is_odd_sign, modality, sign_index
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.features.common import assess_width, assessment_of, points, subject
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.refdata import VargaSpec
from astro.calc.sensitivity import Assessment

DEFAULT_VARGAS = ("D1", "D9", "D10")


def varga_sign(lon: float, spec: VargaSpec) -> int:
    s = sign_index(lon)
    if spec.rule == "same":
        offset = 0
    elif spec.rule == "by_parity":
        offset = spec.offsets["odd" if is_odd_sign(s) else "even"]
    else:
        offset = spec.offsets[modality(s)]
    # scale first so a longitude exactly on a part boundary lands in the later part
    part = min(int(deg_in_sign(lon) * spec.divisions // 30.0), spec.divisions - 1)
    return (s + offset + part) % 12


class Vargas:
    id = "vargas"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        vargas = tuple(params.get("vargas", DEFAULT_VARGAS))
        specs = {v: ctx.refdata.varga_spec(v) for v in vargas}
        facts: list[ChartFact] = []
        signs: dict[tuple[str, str], int | None] = {}
        assessments: dict[tuple[str, int], Assessment] = {}
        for body in points(ctx):
            subj = subject(body)
            lon_f = pos.fact("longitude", subj)
            for v, spec in specs.items():
                if lon_f.value is None:
                    facts.append(ctx.unknown("varga_sign", subj, varga=v))
                    signs[(subj, v)] = None
                    continue
                vs = varga_sign(float(lon_f.value), spec)
                signs[(subj, v)] = vs
                a = assessments.setdefault((subj, spec.divisions),
                                           self._assess(ctx, body, pos, spec.divisions))
                facts.append(ctx.fact("varga_sign", subj, ctx.refdata.rashi_id(vs), varga=v,
                                      sensitivity=a.sensitivity, margins=a.margins))
        if "D9" in specs:
            d9 = specs["D9"]
            for body in points(ctx):
                subj = subject(body)
                if signs[(subj, "D9")] is None:
                    facts.append(ctx.unknown("vargottama", subj))
                    continue
                lon = float(pos.fact("longitude", subj).value)
                # D9 boundaries include every sign boundary, so the D9 assessment suffices
                a = assessments[(subj, d9.divisions)]
                facts.append(ctx.fact("vargottama", subj, varga_sign(lon, d9) == sign_index(lon),
                                      sensitivity=a.sensitivity, margins=a.margins))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance={"vargas": vargas})

    @staticmethod
    def _assess(ctx: ChartContext, body: str, pos: FeatureResult, divisions: int) -> Assessment:
        # D1 boundaries are signs and D9 boundaries are padas: reuse the positions assessment
        kind = {1: "sign", 9: "pada"}.get(divisions)
        if kind is not None:
            return assessment_of(pos.fact(kind, subject(body)))
        return assess_width(ctx, body, 30.0 / divisions)


