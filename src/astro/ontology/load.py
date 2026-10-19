"""Loading the ontology and checking its integrity (design §8, phase1-foundations §3.2, §3.4).

`load_ontology(directory)` reads every `ontology/*.yaml` section listed in `SECTIONS` into typed
entities and runs the checks; any problem raises `OntologyError` listing all of them.

Checks:
1. every referenced ID resolves;
2. a folded alias is a plain name of at most one entity;
3. an alias ambiguous anywhere is ambiguous everywhere (never a plain name elsewhere);
4. a disputed value (a list of views) has a source on each view;
5. a file marked `reviewed` cites `<edition_id>:<locator>` with a registered edition;
6. the calculation's own table checks (`YamlReferenceData`) pass;
7. every ID the calculation emits is an entity;
8. core kinds have at least one Latin and one Devanagari name (KNW-1);
9. there are 12 houses, and their ordinals are single words used once.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML

from astro.calc.core.canonical import content_hash
from astro.calc.core.files import VersionedCache, stamp
from astro.calc.features.condition import DIGNITIES
from astro.calc.refdata import IntegrityError, YamlReferenceData
from astro.ontology.fold import FOLD_VERSION, key
from astro.ontology.model import (
    Attrs,
    Bhava,
    BhavaGroup,
    DashaSystem,
    Entity,
    Graha,
    KarakaScheme,
    Listed,
    Lorded,
    Ontology,
    Topic,
    Varga,
    Yoga,
)


class OntologyError(ValueError):
    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


# (file, section, kind, model, layout); `list` entries carry their own `id`, `numbered` entries
# are bhava:1…12 by position, `map` keys are the slugs
SECTIONS: tuple[tuple[str, str, str, type[Attrs], str], ...] = (
    ("grahas", "grahas", "graha", Graha, "map"),
    ("rashis", "rashis", "rashi", Lorded, "list"),
    ("nakshatras", "nakshatras", "nakshatra", Lorded, "list"),
    ("bhavas", "bhavas", "bhava", Bhava, "numbered"),
    ("bhavas", "bhava_groups", "bhava_group", BhavaGroup, "map"),
    ("dignities", "dignities", "dignity", Attrs, "map"),
    ("panchanga", "tithis", "tithi", Listed, "list"),
    ("panchanga", "pakshas", "paksha", Listed, "list"),
    ("panchanga", "varas", "vara", Lorded, "list"),
    ("panchanga", "nitya_yogas", "nitya_yoga", Listed, "list"),
    ("panchanga", "karanas", "karana", Listed, "karanas"),
    ("vargas", "vargas", "varga", Varga, "map"),
    ("dasha_systems", "dasha_systems", "dasha_system", DashaSystem, "map"),
    ("karaka_schemes", "karaka_schemes", "karaka_scheme", KarakaScheme, "map"),
    ("yogas", "yogas", "yoga", Yoga, "map"),
    ("points", "points", "point", Attrs, "map"),
    ("points", "upagrahas", "upagraha", Attrs, "map"),
    ("points", "special_lagnas", "special_lagna", Attrs, "map"),
    ("deities", "deities", "deity", Attrs, "map"),
    ("topics", "topics", "topic", Topic, "map"),
    ("methods", "schools", "school", Attrs, "map"),
    ("kootas", "kootas", "koota", Attrs, "map"),
)

# kinds whose entities need a Latin and a Devanagari name (KNW-1); the others get them as the
# content is reviewed
SCRIPT_KINDS = frozenset({"graha", "rashi", "nakshatra", "bhava", "dignity", "tithi", "paksha",
                          "vara", "nitya_yoga", "karana", "varga"})
# IDs the calculation writes literally (calc/features/panchanga.py, calc/features/common.py)
ENGINE_LITERALS = {"paksha:shukla": "paksha:shukla", "paksha:krishna": "paksha:krishna",
                   "lagna": "point:lagna"}
SOURCE_REF = re.compile(r"^([a-z0-9_]+):(\S+)$")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _entries(raw: Any, layout: str) -> Iterable[tuple[str, dict]]:
    if layout == "map":
        for slug, attrs in (raw or {}).items():
            yield str(slug), dict(attrs or {})
    elif layout == "list":
        for attrs in raw:
            yield attrs["id"], dict(attrs)
    elif layout == "numbered":
        for i, attrs in enumerate(raw, start=1):
            yield str(i), dict(attrs)
    elif layout == "karanas":
        for attrs in [*raw["movable"], *raw["fixed"].values()]:
            yield attrs["id"], dict(attrs)


def _read(directory: Path) -> tuple[dict[str, Any], list[str]]:
    y = YAML(typ="safe")
    files, errors = {}, []
    for name in sorted({s[0] for s in SECTIONS}):
        path = directory / f"{name}.yaml"
        if not path.exists():
            errors.append(f"{name}.yaml: missing")
            continue
        files[name] = y.load(path.read_text(encoding="utf-8"))
    return files, errors


def _build(files: dict[str, Any], errors: list[str]) -> dict[str, Entity]:
    entities: dict[str, Entity] = {}
    for fname, section, kind, model, layout in SECTIONS:
        if fname not in files:
            continue
        raw = files[fname].get(section)
        if raw is None:
            errors.append(f"{fname}.yaml: section {section!r} missing")
            continue
        for slug, attrs in _entries(raw, layout):
            eid = f"{kind}:{slug}"
            try:
                parsed = model.model_validate(attrs)
            except ValidationError as e:
                errors.append(f"{fname}.yaml: {eid}: " + "; ".join(
                    f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))
                continue
            if eid in entities:
                errors.append(f"{fname}.yaml: duplicate entity {eid}")
            entities[eid] = Entity(eid, kind, f"{fname}.yaml", parsed)
    return entities


def _references(e: Entity) -> Iterable[tuple[str, str]]:
    """(referenced ID, where) for each ID an entity refers to."""
    a = e.attrs
    if isinstance(a, Graha):
        yield from ((s, "own_signs") for s in a.own_signs)
        for name in ("exaltation", "debilitation", "moolatrikona"):
            v = getattr(a, name)
            for view in (v if isinstance(v, tuple) else (v,) if v else ()):
                yield view.sign, name
        if a.natural_friendship:
            nf = a.natural_friendship
            yield from ((f"graha:{g}", "natural_friendship")
                        for g in (*nf.friends, *nf.neutral, *nf.enemies))
    if isinstance(a, Lorded):
        yield f"graha:{a.lord}", "lord"
    if isinstance(a, Bhava):
        yield from ((g, "karakas") for g in a.karakas)
    if isinstance(a, BhavaGroup):
        yield from ((f"bhava:{m}", "members") for m in a.members)
    if isinstance(a, DashaSystem):
        yield from ((f"graha:{i['lord']}", "sequence") for i in a.sequence)
    if isinstance(a, KarakaScheme):
        yield from ((f"graha:{g}", "roles") for g in a.roles)
        yield from ((f"graha:{g}", "native") for g in a.native.values())


def _views(e: Entity) -> Iterable[tuple[str, Any]]:
    """(attribute, view) for each view of a disputed (list-valued) attribute."""
    if isinstance(e.attrs, Graha):
        for name in ("exaltation", "debilitation", "moolatrikona"):
            v = getattr(e.attrs, name)
            if isinstance(v, tuple):
                yield from ((name, view) for view in v)


def check_aliases(entities: dict[str, Entity]) -> list[str]:
    """Rules 2 and 3: plain names unique; ambiguity declared wherever an alias is used."""
    plain: dict[tuple[str, ...], set[str]] = defaultdict(set)
    ambiguous: dict[tuple[str, ...], set[str]] = defaultdict(set)
    errors = []
    for e in entities.values():
        for n in e.attrs.names:
            (plain[key(n)].add(e.id) if key(n) else errors.append(f"{e.id}: empty name {n!r}"))
        for n in e.attrs.ambiguous_names:
            (ambiguous[key(n)].add(e.id) if key(n) else errors.append(f"{e.id}: empty name {n!r}"))
    for k, ids in sorted(plain.items()):
        alias = " ".join(k)
        if len(ids) > 1:
            errors.append(f"alias {alias!r} is a plain name of {sorted(ids)}; list it under "
                          "ambiguous_names of each, or rename")
        if k in ambiguous and ambiguous[k] - ids:
            errors.append(f"alias {alias!r} is a plain name of {sorted(ids)} but ambiguous for "
                          f"{sorted(ambiguous[k] - ids)}; make it ambiguous everywhere")
    return errors


def _check(directory: Path, files: dict[str, Any], entities: dict[str, Entity],
           editions: frozenset[str]) -> list[str]:
    errors = []
    # 1. references
    for e in entities.values():
        for ref, where in _references(e):
            if ref not in entities:
                errors.append(f"{e.file}: {e.id}.{where}: unknown {ref}")
    # 2, 3. aliases
    errors += check_aliases(entities)
    # 4. disputed values carry sources
    for e in entities.values():
        for name, view in _views(e):
            if not view.source:
                errors.append(f"{e.file}: {e.id}.{name}: every disputed view needs a source")
    # 5. reviewed files cite registered editions
    for fname, data in files.items():
        meta = (data or {}).get("meta") or {}
        if meta.get("status") not in ("provisional", "reviewed"):
            errors.append(f"{fname}.yaml: meta.status must be provisional or reviewed")
        if meta.get("status") != "reviewed":
            continue
        cited = [meta.get("source")] + [v.source for e in entities.values()
                                        if e.file == f"{fname}.yaml" for _, v in _views(e)]
        for src in cited:
            m = SOURCE_REF.match(src or "")
            if not m or m.group(1) not in editions:
                errors.append(f"{fname}.yaml: reviewed, so source {src!r} must be "
                              "<edition_id>:<locator> with the edition in sources/register.yaml")
    # 6, 7. the calculation's view agrees
    try:
        ref = YamlReferenceData(directory)
    except (IntegrityError, KeyError, TypeError) as e:
        errors.append(f"calculation reference data: {e}")
    else:
        emitted = {ref.rashi_id(i) for i in range(12)} | {ref.nakshatra_id(i) for i in range(27)}
        emitted |= {ref.tithi_id(i) for i in range(30)} | {ref.karana_id(i) for i in range(60)}
        emitted |= {ref.nitya_yoga_id(i) for i in range(27)} | {ref.vara(i)[0] for i in range(7)}
        emitted |= {f"varga:{v}" for v in ref.varga_ids()}
        emitted |= {f"dignity:{d}" for d in DIGNITIES} | set(ENGINE_LITERALS.values())
        emitted |= {f"dasha_system:{s}" for s in files.get("dasha_systems", {})
                    .get("dasha_systems", {})}
        for eid in sorted(emitted - set(entities)):
            errors.append(f"the calculation emits {eid}, which is not an ontology entity")
    # 8. scripts
    for e in entities.values():
        if e.kind not in SCRIPT_KINDS:
            continue
        names = (*e.attrs.names, *e.attrs.ambiguous_names)
        if not any(_DEVANAGARI.search(n) for n in names) or \
                all(_DEVANAGARI.search(n) for n in names):
            errors.append(f"{e.file}: {e.id}: needs a Latin and a Devanagari name (KNW-1)")
    # 9. houses
    bhavas = [e for e in entities.values() if e.kind == "bhava"]
    if len(bhavas) != 12:
        errors.append(f"bhavas.yaml: expected 12 houses, found {len(bhavas)}")
    seen: dict[tuple[str, ...], str] = {}
    for e in bhavas:
        for o in e.attrs.ordinals:
            if len(key(o)) != 1:
                errors.append(f"bhavas.yaml: {e.id}: ordinal {o!r} must be one word")
            if key(o) in seen:
                errors.append(f"bhavas.yaml: ordinal {o!r} used by {seen[key(o)]} and {e.id}")
            seen[key(o)] = e.id
    return errors


def load_ontology(directory: Path, editions: Iterable[str] = ()) -> Ontology:
    """Every entity in `directory`, integrity-checked; `editions` are the registered edition IDs
    that reviewed files may cite. Raises `OntologyError` with every problem found."""
    directory = Path(directory)
    files, errors = _read(directory)
    entities = _build(files, errors)
    if not errors:
        errors += _check(directory, files, entities, frozenset(editions))
    if errors:
        raise OntologyError(errors)
    file_status = {f"{n}.yaml": d["meta"]["status"] for n, d in files.items()}
    return Ontology(
        entities=entities,
        version=content_hash({"files": files, "fold": FOLD_VERSION})[:16],
        status="reviewed" if set(file_status.values()) == {"reviewed"} else "provisional",
        file_status=file_status,
        house_words=tuple(files["bhavas"].get("house_words", ())),
    )


_CACHE = VersionedCache()


def cached_ontology(directory: Path, editions: Iterable[str] = ()) -> Ontology:
    """`load_ontology`, once per version of the files (an edited file is reloaded)."""
    d = Path(directory).resolve()
    eds = tuple(sorted(editions))
    return _CACHE.get((d, eds), stamp(d), lambda: load_ontology(d, eds))
