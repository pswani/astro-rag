"""Offline place lookup (INP-1, design §6.2.2).

`CityTable` reads the GeoNames-derived city table shipped with the `reverse_geocode` package
(155k places with population ≥ 1000; GeoNames data, CC BY 4.0). It is a stand-in for the full
GeoNames dump (task B4.5) behind the same `Gazetteer` interface.

Rules from the design: no country preference; the supplied country/region narrows the match;
population may order candidates but never establishes identity, so more than one plausible place
is returned as ambiguous for the caller to clarify. The nearest town is never substituted.
"""

from __future__ import annotations

import csv
import difflib
import gzip
import importlib.util
import json
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, Protocol

ATTRIBUTION = "Place data: GeoNames (geonames.org), CC BY 4.0, via the reverse_geocode package"

# everyday names for countries whose table name or ISO code people rarely type
COUNTRY_ALIASES = {"uk": "GB", "great britain": "GB", "britain": "GB", "usa": "US",
                   "united states of america": "US", "america": "US", "uae": "AE",
                   "south korea": "KR", "north korea": "KP", "russia": "RU", "iran": "IR",
                   "vietnam": "VN", "laos": "LA", "syria": "SY", "bolivia": "BO",
                   "venezuela": "VE", "tanzania": "TZ", "czechia": "CZ", "holland": "NL"}


@dataclass(frozen=True)
class Place:
    name: str
    state: str
    country_code: str
    country: str
    latitude: float
    longitude: float
    population: int
    geonames_id: int | None = None  # the cities1000 table in reverse_geocode carries none

    def provenance(self, source: str, query: str) -> dict:
        return {"source": source, "query": query, "label": self.label, "name": self.name,
                "state": self.state, "country_code": self.country_code,
                "latitude": self.latitude, "longitude": self.longitude,
                "geonames_id": self.geonames_id}

    @property
    def label(self) -> str:
        parts = [self.name, self.state, self.country]
        return ", ".join(p for p in parts if p)


@dataclass(frozen=True)
class Lookup:
    status: Literal["found", "ambiguous", "not_found"]
    candidates: tuple[Place, ...] = ()
    suggestions: tuple[str, ...] = ()

    @property
    def place(self) -> Place:
        if self.status != "found":
            raise ValueError(f"lookup is {self.status}")
        return self.candidates[0]


class Gazetteer(Protocol):
    source: str

    def lookup(self, query: str, limit: int = 10) -> Lookup: ...


def fold(text: str) -> str:
    """Case- and accent-insensitive key: 'São Paulo' → 'sao paulo'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c))
                    .casefold().replace("-", " ").split())


def _data_dir() -> Path:
    spec = importlib.util.find_spec("reverse_geocode")
    if spec is None or spec.origin is None:
        raise RuntimeError("place lookup needs the `reverse_geocode` package "
                           "(pip install 'astro[geo]'); or pass --lat/--lon")
    return Path(spec.origin).parent


class CityTable:
    source = "geonames-cities1000 (reverse_geocode)"

    def __init__(self, data_dir: Path | None = None) -> None:
        d = data_dir or _data_dir()
        with (d / "countries.csv").open(encoding="utf-8") as fh:
            self._countries = {row[0]: row[1] for row in csv.reader(fh) if row}
        with gzip.open(d / "geocode.gz", "rt", encoding="utf-8") as fh:
            rows = json.load(fh)
        self._by_name: dict[str, list[Place]] = {}
        for r in rows:
            p = Place(r["city"], r.get("state") or "", r["country_code"],
                      self._countries.get(r["country_code"], r["country_code"]),
                      float(r["latitude"]), float(r["longitude"]), int(r.get("population") or 0))
            self._by_name.setdefault(fold(p.name), []).append(p)
        self._country_keys = {fold(code): code for code in self._countries}
        self._country_keys.update({fold(name): code for code, name in self._countries.items()})
        self._country_keys.update(COUNTRY_ALIASES)

    def _country(self, text: str) -> str | None:
        return self._country_keys.get(fold(text))

    def lookup(self, query: str, limit: int = 10) -> Lookup:
        parts = [p.strip() for p in query.split(",") if p.strip()]
        if not parts:
            return Lookup("not_found")
        name, qualifiers = fold(parts[0]), parts[1:]
        candidates = list(self._by_name.get(name, []))
        if not candidates:
            close = difflib.get_close_matches(name, self._by_name.keys(), n=25, cutoff=0.7)
            near = _ordered([p for k in close for p in self._by_name[k]])
            return Lookup("not_found", suggestions=tuple(p.label for p in near[:limit]))
        for q in qualifiers:
            # A qualifier can be a country or a state ("CA" is Canada and California,
            # "Georgia" a country and a US state), so both readings narrow the candidates.
            code = self._country(q)
            fq = fold(q)
            by_country = [p for p in candidates if p.country_code == code] if code else []
            exact_state = [p for p in candidates if fold(p.state) == fq]
            by_state = exact_state or [p for p in candidates if fold(p.state).startswith(fq)]
            narrowed = by_country + [p for p in by_state if p not in by_country]
            if not narrowed:
                return Lookup("not_found", suggestions=tuple(
                    p.label for p in _ordered(candidates)[:limit]))
            candidates = narrowed
        ordered = tuple(_ordered(candidates)[:limit])
        return Lookup("found" if len(candidates) == 1 else "ambiguous", ordered)


def _ordered(places: list[Place]) -> list[Place]:
    # population only orders the list shown to the user; it never picks the place
    return sorted(places, key=lambda p: (-p.population, p.country_code, p.state))


@cache
def default_gazetteer() -> CityTable:
    return CityTable()
