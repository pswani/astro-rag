"""The alias matcher: text → ontology entities (design §8, §9.6; phase1-foundations §3.6).

Deterministic and longest-match-first over folded tokens, so "Shiva yoga" is one span
(nitya_yoga:shiva), not deity:shiva + "yoga". A span is resolved to one entity or reported as
ambiguous with its candidates; the matcher never picks between readings. An ambiguous span with
one candidate means "this entity or an ordinary word" (Guru: Jupiter, or a teacher).

`reserved` adds candidates the ontology does not know, such as the labels of stored persons, so
"Ravi" with a stored person Ravi is ambiguous instead of the Sun.

House ordinals are a closed pattern: an ordinal followed by a house word ("10th house",
"दशम भाव") is bhava:10. A bare ordinal is left to the planner.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from astro.ontology.fold import key, tokens
from astro.ontology.model import Bhava, Ontology


@dataclass(frozen=True)
class Span:
    start: int                      # offsets into the NFC form of the text
    end: int
    text: str
    candidates: tuple[str, ...]     # one entity when resolved
    ambiguous: bool

    @property
    def entity_id(self) -> str | None:
        return None if self.ambiguous else self.candidates[0]


@dataclass(frozen=True)
class _Entry:
    candidates: frozenset[str]
    ambiguous: bool


class AliasMatcher:
    def __init__(self, ontology: Ontology) -> None:
        table: dict[tuple[str, ...], tuple[set[str], set[str]]] = {}
        ordinals: dict[str, str] = {}
        for e in ontology.entities.values():
            for n in e.attrs.names:
                table.setdefault(key(n), (set(), set()))[0].add(e.id)
            for n in e.attrs.ambiguous_names:
                table.setdefault(key(n), (set(), set()))[1].add(e.id)
            if isinstance(e.attrs, Bhava):
                for o in e.attrs.ordinals:
                    (k,) = key(o)
                    ordinals[k] = e.id
        # the load-time checks guarantee a plain name belongs to one entity and is never also
        # ambiguous elsewhere; a name listed only as ambiguous stays ambiguous
        self._table = {k: _Entry(frozenset(p | a), bool(a) or len(p) > 1)
                       for k, (p, a) in table.items()}
        self._ordinals = ordinals
        self._house_words = frozenset(w for h in ontology.house_words for w in key(h))
        self._longest = max(len(k) for k in self._table)

    def match(self, text: str, reserved: Mapping[str, Sequence[str]] | None = None) -> list[Span]:
        """Entity spans in `text`, left to right, without overlaps. `reserved` maps extra names
        (e.g. person labels) to the candidates they stand for."""
        extra: dict[tuple[str, ...], frozenset[str]] = {}
        for name, cands in (reserved or {}).items():
            if key(name):
                extra[key(name)] = extra.get(key(name), frozenset()) | frozenset(cands)
        longest = max([self._longest, *map(len, extra)])
        toks = tokens(text)
        folded = [t for _, _, t in toks]
        nfc_text = unicodedata.normalize("NFC", text)
        out, i = [], 0
        while i < len(toks):
            if folded[i] in self._ordinals and i + 1 < len(toks) and \
                    folded[i + 1] in self._house_words:
                out.append(self._span(nfc_text, toks, i, 2, frozenset({self._ordinals[folded[i]]}),
                                      False))
                i += 2
                continue
            for n in range(min(longest, len(toks) - i), 0, -1):
                k = tuple(folded[i:i + n])
                hit, more = self._table.get(k), extra.get(k)
                if hit is None and more is None:
                    continue
                cands = (hit.candidates if hit else frozenset()) | (more or frozenset())
                ambiguous = (hit.ambiguous if hit else True) or bool(more)
                out.append(self._span(nfc_text, toks, i, n, cands, ambiguous))
                i += n
                break
            else:
                i += 1
        return out

    @staticmethod
    def _span(text: str, toks: list, i: int, n: int, cands: frozenset[str],
              ambiguous: bool) -> Span:
        start, end = toks[i][0], toks[i + n - 1][1]
        return Span(start, end, text[start:end], tuple(sorted(cands)), ambiguous)
