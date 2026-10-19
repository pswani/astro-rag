"""Shared fixtures for calculation tests."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from astro.calc.ephemeris.swiss import SwissEphemeris
from astro.calc.profile import CalcProfile, load_profiles
from astro.calc.refdata import YamlReferenceData

ROOT = Path(__file__).resolve().parents[2]
EPHE = ROOT / "data" / "ephe"


@cache
def profiles() -> dict[str, CalcProfile]:
    return load_profiles(ROOT / "profiles" / "calc")


def profile(pid: str = "parashari_v1") -> CalcProfile:
    return profiles()[pid]


@cache
def ephemeris() -> SwissEphemeris:
    return SwissEphemeris(EPHE, profile())


@cache
def refdata() -> YamlReferenceData:
    return YamlReferenceData(ROOT / "ontology")
