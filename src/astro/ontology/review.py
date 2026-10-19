"""The review pack: every entity with its names and attributes, as one Markdown document for the
astrologer's review (phase-1 exit "ontology reviewed"; phase1-foundations §3.8)."""

from __future__ import annotations

from astro.ontology.load import SECTIONS
from astro.ontology.model import Ontology


def _cell(v) -> str:
    if isinstance(v, (list, tuple)):
        v = ", ".join(_cell(x) for x in v)
    elif isinstance(v, dict):
        v = "; ".join(f"{k}: {_cell(x)}" for k, x in v.items())
    return str(v).replace("|", "\\|").replace("\n", " ")


def review_pack(ontology: Ontology) -> str:
    lines = [
        "# Ontology review pack",
        "",
        f"Version `{ontology.version}`, status **{ontology.status}**. For each entity, check the "
        "ID, every name (plain names are matched in text; ambiguous names are only reported as "
        "possible matches), and the attributes. Note corrections, missing names and the source "
        "edition and locator for each value.",
        "",
        "| File | Status |",
        "|---|---|",
        *(f"| {f} | {s} |" for f, s in sorted(ontology.file_status.items())),
    ]
    for _, _, kind, _, _ in SECTIONS:
        entities = ontology.of_kind(kind)
        if not entities:
            continue
        lines += ["", f"## {kind} ({len(entities)})", "",
                  "| ID | Names | Ambiguous names | Attributes |", "|---|---|---|---|"]
        for e in entities:
            attrs = e.attrs.model_dump(exclude={"names", "ambiguous_names"}, exclude_none=True,
                                       by_alias=True)
            lines.append(f"| `{e.id}` | {_cell(e.attrs.names)} | {_cell(e.attrs.ambiguous_names)}"
                         f" | {_cell(attrs)} |")
    return "\n".join(lines) + "\n"
