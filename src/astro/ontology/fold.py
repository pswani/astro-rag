"""Folding and tokenization for alias matching (phase1-foundations §3.3).

Aliases and text are compared token by token after `fold()`:
- Unicode NFC;
- Latin: combining marks dropped and case folded (Śani → sani);
- Devanagari: a class nasal with virama before a consonant of its class becomes an anusvara
  (मङ्गल → मंगल); nukta and zero-width joiners are dropped.

Tokens keep combining marks: Python's `\\w` excludes Devanagari vowel signs, so a plain `\\w+`
would split शनि into शन + ि. Transliteration variants (Shani, Sani) are listed in the ontology,
not guessed here. Changing any rule here changes `FOLD_VERSION`, and with it the ontology version.
"""

from __future__ import annotations

import re
import unicodedata

FOLD_VERSION = "1"

_VIRAMA, _ANUSVARA = "्", "ं"
_NASAL_CLASS = {row[-1]: frozenset(row) for row in
                ("कखगघङ", "चछजझञ", "टठडढण", "तथदधन", "पफबभम")}
_DROP = {"़", "‌", "‍"}  # nukta, ZWNJ, ZWJ
_MARKS = ("̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯"
          "‌‍")
# letters and digits, Latin combining marks, and the Devanagari block except the dandas
TOKEN = re.compile(rf"[\w{_MARKS}ऀ-ॣ०-ॿ]+")


def _devanagari(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in _DROP:
            i += 1
            continue
        if c in _NASAL_CLASS and i + 2 < len(s) and s[i + 1] == _VIRAMA \
                and s[i + 2] in _NASAL_CLASS[c]:
            out.append(_ANUSVARA)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def fold(s: str) -> str:
    s = _devanagari(unicodedata.normalize("NFC", s))
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if not (unicodedata.combining(c) and not "ऀ" <= c <= "ॿ"))
    return unicodedata.normalize("NFC", s).casefold()


def tokens(text: str) -> list[tuple[int, int, str]]:
    """(start, end, folded token) for each token; offsets refer to the NFC form of `text`."""
    nfc = unicodedata.normalize("NFC", text)
    return [(m.start(), m.end(), fold(m.group())) for m in TOKEN.finditer(nfc)]


def key(alias: str) -> tuple[str, ...]:
    """The folded token sequence an alias is matched by."""
    return tuple(t for _, _, t in tokens(alias))
