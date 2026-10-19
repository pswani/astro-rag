"""Read-only reference data for the calculation service (KNW-11, calc-review M6).

Calculations read canonical tables from the ontology through this narrow interface, never from
the passage index. `YamlReferenceData` loads `ontology/*.yaml` and checks referential integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from ruamel.yaml import YAML

from astro.calc.core.canonical import content_hash

Friendship = Literal["friend", "neutral", "enemy"]

GRAHAS_7 = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")
GRAHAS_9 = (*GRAHAS_7, "rahu", "ketu")


@dataclass(frozen=True)
class Dignities:
    exaltation: tuple[int, float]          # (sign, degree)
    debilitation: tuple[int, float]
    moolatrikona: tuple[int, float, float]  # (sign, from, to)


@dataclass(frozen=True)
class VargaSpec:
    id: str
    divisions: int
    rule: Literal["same", "by_parity", "by_modality", "by_element", "table"]
    offsets: dict[str, int]  # keys: odd/even, movable/fixed/dual or fire/earth/air/water
    basis: Literal["relative", "absolute"] = "relative"
    step: int = 1
    table: dict[str, tuple[tuple[float, int], ...]] | None = None  # parity → (end°, sign)

    def boundaries(self) -> list[float]:
        """Absolute longitudes of every part boundary of a table varga (for sensitivity);
        equal-part vargas use the part width instead."""
        if self.table is None:
            raise ValueError(f"{self.id} has equal parts: use 30 / divisions")
        out = []
        for s in range(12):
            parts = self.table["odd" if s % 2 == 0 else "even"]
            out += [s * 30.0] + [s * 30.0 + end for end, _ in parts[:-1]]
        return out


class ReferenceData(Protocol):
    version: str

    def rashi_id(self, sign: int) -> str: ...
    def rashi_index(self, rashi: str) -> int: ...
    def sign_lord(self, sign: int) -> str: ...
    def own_signs(self, graha: str) -> tuple[int, ...]: ...
    def dignities(self, graha: str) -> Dignities | None: ...
    def nakshatra_id(self, index: int) -> str: ...
    def nakshatra_lord(self, index: int) -> str: ...
    def natural_friendship(self, graha: str, other: str) -> Friendship | None: ...
    def dasha_sequence(self, system: str) -> tuple[tuple[str, float], ...]: ...
    def varga_spec(self, varga: str) -> VargaSpec: ...
    def tithi_id(self, index: int) -> str: ...
    def karana_id(self, index: int) -> str: ...
    def nitya_yoga_id(self, index: int) -> str: ...
    def vara(self, weekday: int) -> tuple[str, str]: ...
    def karaka_roles(self, scheme: str, graha: str) -> tuple[str, ...]: ...
    def native_karaka(self, scheme: str, gender: str) -> str | None: ...


class IntegrityError(ValueError):
    pass


def _strip(prefixed: str, kind: str) -> str:
    if not prefixed.startswith(kind + ":"):
        raise IntegrityError(f"{prefixed!r} is not a {kind}: ID")
    return prefixed.split(":", 1)[1]


class YamlReferenceData:
    def __init__(self, directory: Path) -> None:
        y = YAML(typ="safe")
        load = lambda name: y.load((Path(directory) / f"{name}.yaml").read_text())  # noqa: E731
        self._grahas = load("grahas")["grahas"]
        self._rashis = load("rashis")["rashis"]
        self._naks = load("nakshatras")["nakshatras"]
        pan = load("panchanga")
        self._tithis = pan["tithis"]
        self._karanas = pan["karanas"]
        self._yogas = pan["nitya_yogas"]
        self._varas = pan["varas"]
        self._dashas = load("dasha_systems")["dasha_systems"]
        self._vargas = load("vargas")["vargas"]
        self._karakas = load("karaka_schemes")["karaka_schemes"]
        statuses = {load(n)["meta"]["status"] for n in
                    ("grahas", "rashis", "nakshatras", "panchanga", "dasha_systems", "vargas",
                     "karaka_schemes")}
        self.status = "provisional" if "provisional" in statuses else "reviewed"
        self.version = content_hash({
            "g": self._grahas, "r": self._rashis, "n": self._naks, "t": self._tithis,
            "k": self._karanas, "y": self._yogas, "v": self._varas, "d": self._dashas,
            "vg": self._vargas, "ks": self._karakas})[:16]
        self._rashi_index = {r["id"]: i for i, r in enumerate(self._rashis)}
        self.check()

    # -- integrity (CI: every referenced ID resolves) ---------------------------------------
    def check(self) -> None:
        if len(self._rashis) != 12 or len(self._naks) != 27:
            raise IntegrityError("expected 12 rashis and 27 nakshatras")
        if len(self._tithis) != 30 or len(self._yogas) != 27 or len(self._varas) != 7:
            raise IntegrityError("expected 30 tithis, 27 nitya yogas, 7 varas")
        if len(self._karanas["movable"]) != 7 or set(self._karanas["fixed"]) != {0, 57, 58, 59}:
            raise IntegrityError("karanas: 7 movable and fixed at 0, 57, 58, 59")
        if set(self._grahas) != set(GRAHAS_9):
            raise IntegrityError(f"grahas must be exactly {GRAHAS_9}")
        for r in self._rashis:
            self._need_graha(r["lord"], f"rashi {r['id']}")
        for n in self._naks:
            self._need_graha(n["lord"], f"nakshatra {n['id']}")
        for v in self._varas:
            self._need_graha(v["lord"], f"vara {v['id']}")
        for g, attrs in self._grahas.items():
            for s in attrs.get("own_signs", []):
                if _strip(s, "rashi") not in self._rashi_index:
                    raise IntegrityError(f"{g}: unknown sign {s}")
                if self._rashis[self._rashi_index[_strip(s, "rashi")]]["lord"] != g:
                    raise IntegrityError(f"{g} owns {s} but the rashi table disagrees")
            nf = attrs.get("natural_friendship")
            if g in GRAHAS_7:
                if nf is None:
                    raise IntegrityError(f"{g}: natural friendship missing")
                listed = [o for k in ("friends", "neutral", "enemies") for o in nf[k]]
                if sorted(listed) != sorted(set(GRAHAS_7) - {g}):
                    raise IntegrityError(f"{g}: friendship must classify each other graha once")
        for name, sysd in self._dashas.items():
            seq = sysd["sequence"]
            for item in seq:
                self._need_graha(item["lord"], f"dasha {name}")
            if abs(sum(i["years"] for i in seq) - sysd["total_years"]) > 1e-9:
                raise IntegrityError(f"dasha {name}: years do not sum to total")
        for vid in self._vargas:
            self.varga_spec(vid)
        for scheme, data in self._karakas.items():
            for g in data["roles"]:
                self._need_graha(g, f"karaka scheme {scheme}")
            for g in data.get("native", {}).values():
                self._need_graha(g, f"karaka scheme {scheme}")
        for g in GRAHAS_7:
            d = self.dignities(f"graha:{g}")
            if d is None:
                raise IntegrityError(f"{g}: exaltation, debilitation and moolatrikona needed")
            if d.debilitation[0] != (d.exaltation[0] + 6) % 12 or \
                    d.debilitation[1] != d.exaltation[1]:
                raise IntegrityError(f"{g}: debilitation must oppose exaltation")
            mt_sign, lo, hi = d.moolatrikona
            if mt_sign not in (*self.own_signs(f"graha:{g}"), d.exaltation[0]) or \
                    not 0 <= lo < hi <= 30:
                raise IntegrityError(f"{g}: moolatrikona must lie in an own or exaltation sign")
        # nakshatra lords follow the Vimshottari order from Ashwini
        vim = [i["lord"] for i in self._dashas["vimshottari"]["sequence"]]
        if [n["lord"] for n in self._naks] != vim * 3:
            raise IntegrityError("nakshatra lords must follow the Vimshottari order")

    def _need_graha(self, g: str, where: str) -> None:
        if g not in self._grahas:
            raise IntegrityError(f"{where}: unknown graha {g!r}")

    # -- lookups -----------------------------------------------------------------------------
    def rashi_id(self, sign: int) -> str:
        return "rashi:" + self._rashis[sign % 12]["id"]

    def rashi_index(self, rashi: str) -> int:
        return self._rashi_index[_strip(rashi, "rashi")]

    def sign_lord(self, sign: int) -> str:
        return "graha:" + self._rashis[sign % 12]["lord"]

    def own_signs(self, graha: str) -> tuple[int, ...]:
        g = _strip(graha, "graha")
        return tuple(self._rashi_index[_strip(s, "rashi")]
                     for s in self._grahas[g].get("own_signs", []))

    def dignities(self, graha: str) -> Dignities | None:
        a = self._grahas[_strip(graha, "graha")]
        if not all(k in a for k in ("exaltation", "debilitation", "moolatrikona")):
            return None
        ri = lambda s: self._rashi_index[_strip(s, "rashi")]  # noqa: E731
        mt = a["moolatrikona"]
        return Dignities((ri(a["exaltation"]["sign"]), float(a["exaltation"]["degree"])),
                         (ri(a["debilitation"]["sign"]), float(a["debilitation"]["degree"])),
                         (ri(mt["sign"]), float(mt["from"]), float(mt["to"])))

    def nakshatra_id(self, index: int) -> str:
        return "nakshatra:" + self._naks[index]["id"]

    def nakshatra_lord(self, index: int) -> str:
        return "graha:" + self._naks[index]["lord"]

    def natural_friendship(self, graha: str, other: str) -> Friendship | None:
        nf = self._grahas[_strip(graha, "graha")].get("natural_friendship")
        o = _strip(other, "graha")
        if nf is None:
            return None
        for key, label in (("friends", "friend"), ("neutral", "neutral"), ("enemies", "enemy")):
            if o in nf[key]:
                return label  # type: ignore[return-value]
        return None

    def dasha_sequence(self, system: str) -> tuple[tuple[str, float], ...]:
        return tuple(("graha:" + i["lord"], float(i["years"]))
                     for i in self._dashas[system]["sequence"])

    def varga_spec(self, varga: str) -> VargaSpec:
        s = self._vargas[varga]
        n = int(s["divisions"])
        if s["parts"] == "table":
            table = {}
            for parity in ("odd", "even"):
                rows = tuple((float(e), int(sign)) for e, sign in s["table"][parity])
                ends = [e for e, _ in rows]
                if ends != sorted(ends) or ends[-1] != 30 or not all(0 <= x < 12 for _, x in rows):
                    raise IntegrityError(f"{varga}: table parts must end at 30° in order")
                table[parity] = rows
            return VargaSpec(varga, n, "table", {}, table=table)
        if s["parts"] != "equal":
            raise IntegrityError(f"{varga}: parts must be equal or table")
        start = dict(s["start"])
        rule = start.pop("rule")
        basis = start.pop("basis", "relative")
        need = {"same": set(), "by_parity": {"odd", "even"},
                "by_modality": {"movable", "fixed", "dual"},
                "by_element": {"fire", "earth", "air", "water"}}.get(rule)
        if need is None or set(start) != need or basis not in ("relative", "absolute"):
            raise IntegrityError(f"{varga}: bad start rule {s['start']}")
        return VargaSpec(varga, n, rule, {k: int(v) for k, v in start.items()}, basis=basis,
                         step=int(s.get("step", 1)))

    def varga_ids(self) -> tuple[str, ...]:
        return tuple(self._vargas)

    def tithi_id(self, index: int) -> str:
        return "tithi:" + self._tithis[index]

    def karana_id(self, index: int) -> str:
        fixed = self._karanas["fixed"]
        if index in fixed:
            return "karana:" + fixed[index]
        return "karana:" + self._karanas["movable"][(index - 1) % 7]

    def nitya_yoga_id(self, index: int) -> str:
        return "nitya_yoga:" + self._yogas[index]

    def vara(self, weekday: int) -> tuple[str, str]:
        v = self._varas[weekday]
        return "vara:" + v["id"], "graha:" + v["lord"]

    def karaka_roles(self, scheme: str, graha: str) -> tuple[str, ...]:
        roles = self._karakas[scheme]["roles"].get(_strip(graha, "graha"), [])
        return tuple(f"karaka_role:{scheme}.{r}" for r in roles)

    def native_karaka(self, scheme: str, gender: str) -> str | None:
        g = self._karakas[scheme].get("native", {}).get(gender)
        return "graha:" + g if g else None
