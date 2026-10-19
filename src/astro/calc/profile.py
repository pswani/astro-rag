"""Calculation profiles (CALC-3, design §7.1, calc-review G-P1).

A profile is immutable once used; a change creates `_v<n+1>`. Unknown keys or values are refused
with `unsupported_profile`, so a convention is never silently substituted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML

from astro.calc.core.canonical import content_hash
from astro.calc.core.status import CalcError, Reason


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Ayanamsa(_Strict):
    id: Literal["lahiri", "raman", "krishnamurti", "true_chitra"]
    nutation: bool = True  # reported ayanamsa value only; sidereal positions are unaffected


class Nodes(_Strict):
    model: Literal["mean", "true"]
    retrograde: Literal["always", "by_speed"]


class Position(_Strict):
    origin: Literal["geocentric"] = "geocentric"
    apparent: bool = True


class Vargas(_Strict):
    default: Literal["parashari"] = "parashari"


class DashaCfg(_Strict):
    system: Literal["vimshottari"]
    year_days: float = Field(gt=300, lt=400)
    levels: tuple[Literal["MD", "AD", "PD", "SD"], ...]
    span_years: float = 120.0
    sandhi_margin_days: dict[Literal["MD", "AD"], float]


class Sunrise(_Strict):
    definition: Literal["hindu_rising", "upper_limb_refraction"]


class EphemerisFile(_Strict):
    name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Coverage(_Strict):
    start_jd: float
    end_jd: float

    @model_validator(mode="after")
    def _ordered(self) -> Coverage:
        if not self.start_jd < self.end_jd:
            raise ValueError("coverage start must precede end")
        return self


class EphemerisCfg(_Strict):
    engine: Literal["swisseph"]
    version: str
    files: tuple[EphemerisFile, ...]
    coverage: Coverage


class TimeCfg(_Strict):
    tzdata: str
    delta_t: Literal["swisseph_default"] = "swisseph_default"


class Eclipse(_Strict):
    orb_deg: float = Field(gt=0, le=30)


class Sensitivity(_Strict):
    # sampling steps in minutes for the boundary solver (design-notes §5)
    step_minutes: dict[str, float]


class CalcProfile(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*_v[0-9]+$")
    status: Literal["draft", "active", "withdrawn"]
    zodiac: Literal["sidereal"]
    ayanamsa: Ayanamsa
    nodes: Nodes
    house_system: Literal["whole_sign", "sripati"]
    position: Position = Position()
    vargas: Vargas = Vargas()
    dasha: DashaCfg
    sunrise: Sunrise
    lunar_month: Literal["amanta", "purnimanta"]
    karaka_scheme: Literal["parashari", "bnn"] = "parashari"
    retro_in_previous_sign: bool = False
    eclipse: Eclipse
    sensitivity: Sensitivity
    ephemeris: EphemerisCfg
    time: TimeCfg
    provisional: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _provisional_paths_exist(self) -> CalcProfile:
        for path in self.provisional:
            node: object = self
            for part in path.split("."):
                if isinstance(node, BaseModel) and part in type(node).model_fields:
                    node = getattr(node, part)
                elif isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    raise ValueError(f"provisional path {path!r} does not exist")
        return self

    @property
    def content_hash(self) -> str:
        return content_hash(self)

    def is_covered(self, jd_ut: float) -> bool:
        c = self.ephemeris.coverage
        return c.start_jd <= jd_ut < c.end_jd


def load_profile(path: Path) -> CalcProfile:
    data = YAML(typ="safe").load(Path(path).read_text())
    try:
        return CalcProfile.model_validate(data)
    except ValidationError as e:
        raise CalcError(Reason.UNSUPPORTED_PROFILE, f"{path}: {e}") from e


def load_profiles(directory: Path) -> dict[str, CalcProfile]:
    profiles = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        prof = load_profile(p)
        if prof.id != p.stem:
            raise CalcError(Reason.UNSUPPORTED_PROFILE, f"{p}: id {prof.id!r} != file name")
        profiles[prof.id] = prof
    return profiles
