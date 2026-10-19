"""`astro ontology`: check the ontology, match text against it, render the review pack."""

from __future__ import annotations

import argparse
from pathlib import Path

from astro.ontology import OntologyError, load_ontology
from astro.ontology.matcher import AliasMatcher
from astro.ontology.review import review_pack
from astro.resources import astro_home


def add_parser(sub) -> None:
    o = sub.add_parser("ontology", help="check the ontology, match text, render the review pack")
    osub = o.add_subparsers(dest="action", required=True)
    osub.add_parser("check", help="load every file and run the integrity checks")
    m = osub.add_parser("match", help="show the entities the alias matcher finds in a text")
    m.add_argument("text")
    m.add_argument("--reserve", action="append", default=[], metavar="NAME=ID",
                   help="an extra candidate for a name, e.g. Ravi=person:p_1 (repeatable)")
    r = osub.add_parser("review-pack", help="every entity as one Markdown document")
    r.add_argument("--out", type=Path, help="write to this file instead of stdout")


def _reserved(items: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in items:
        name, eq, ident = item.partition("=")
        if not eq or not name.strip() or not ident.strip():
            raise argparse.ArgumentTypeError(f"--reserve {item!r}: use NAME=ID")
        out.setdefault(name.strip(), []).append(ident.strip())
    return out


def cmd_ontology(args, out, err) -> int:
    directory = astro_home() / "ontology"
    try:
        onto = load_ontology(directory)
    except OntologyError as e:
        err(f"ontology: {len(e.errors)} problem(s) in {directory}")
        for line in e.errors:
            err(f"  {line}")
        return 1
    if args.action == "check":
        out(f"ontology OK: {len(onto.entities)} entities in {len(onto.kinds())} kinds, "
            f"version {onto.version}, {onto.status}")
        provisional = sorted(f for f, s in onto.file_status.items() if s != "reviewed")
        if provisional:
            out(f"provisional (awaiting review): {', '.join(provisional)}")
        return 0
    if args.action == "match":
        try:
            reserved = _reserved(args.reserve)
        except argparse.ArgumentTypeError as e:
            err(str(e))
            return 2
        spans = AliasMatcher(onto).match(args.text, reserved)
        if not spans:
            out("no entities found")
        for s in spans:
            what = (f"ambiguous: {' | '.join(s.candidates)}" if s.ambiguous
                    else s.candidates[0])
            out(f"{s.text}  →  {what}")
        return 0
    text = review_pack(onto)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        err(f"review pack written to {args.out.resolve()}")
    else:
        out(text.rstrip("\n"))
    return 0
