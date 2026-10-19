"""Plain-text rendering of a chart report: South and North Indian charts, tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from astro.calc.core.angles import to_dms
from astro.calc.model import ChartFact, FeatureResult
from astro.cli.fmt import format_offset
from astro.cli.report import ChartReport

BODIES = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu")
ABBR = {"sun": "Su", "moon": "Mo", "mars": "Ma", "mercury": "Me", "jupiter": "Ju",
        "venus": "Ve", "saturn": "Sa", "rahu": "Ra", "ketu": "Ke", "lagna": "As"}
SIGNS = ("aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio",
         "sagittarius", "capricorn", "aquarius", "pisces")
SIGN_ABBR = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")


def title(entity_id: str | None) -> str:
    """'nakshatra:purva_bhadrapada' → 'Purva Bhadrapada'."""
    if entity_id is None:
        return "unknown"
    return entity_id.split(":", 1)[-1].replace("_", " ").title()


def mark(f: ChartFact | None) -> str:
    """'*' when a birth-time change inside the uncertainty interval would change the fact."""
    if f is None or f.sensitivity == "stable":
        return ""
    return "*" if f.sensitivity == "sensitive" else "?"


# -- chart placement -------------------------------------------------------------------------

def placements(report: ChartReport, varga: str) -> tuple[dict[int, list[str]], int | None]:
    """Sign index → labels (e.g. 'Sa(R)'), and the sign of the Lagna (None if unknown)."""
    pos = report.get("positions")
    var = report.get("vargas")
    by_sign: dict[int, list[str]] = {i: [] for i in range(12)}
    lagna_sign = None
    if pos is None:
        return by_sign, None
    for subj in ("lagna", *BODIES):
        s = f"graha:{subj}" if subj != "lagna" else "lagna"
        if varga == "D1":
            f = pos.fact("sign", s)
        elif var is not None:
            try:
                f = var.fact("varga_sign", s, varga=varga)
            except KeyError:
                continue
        else:
            continue
        if f.value is None:
            continue
        idx = SIGNS.index(f.value.split(":", 1)[1])
        label = ABBR[subj]
        if subj not in ("lagna", "rahu", "ketu") and pos.fact("retrograde", s).value:
            label += "(R)"
        label += mark(f)
        if subj == "lagna":
            lagna_sign = idx
        by_sign[idx].append(label)
    return by_sign, lagna_sign


def _wrap(labels: list[str], width: int) -> list[str]:
    lines, cur = [], ""
    for lab in labels:
        nxt = f"{cur} {lab}".strip()
        if len(nxt) > width and cur:
            lines.append(cur)
            cur = lab
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def south_chart(report: ChartReport, varga: str, caption: str) -> list[str]:
    """Fixed-sign 4×4 grid: Pisces top-left, signs run clockwise."""
    by_sign, _ = placements(report, varga)
    cw = 11  # inner cell width; the height grows so a crowded sign never drops a body
    ch = max(3, 1 + max(len(_wrap(v, cw - 1)) for v in by_sign.values()))
    layout = [[11, 0, 1, 2], [10, None, None, 3], [9, None, None, 4], [8, 7, 6, 5]]
    border = "+" + "+".join("-" * cw for _ in range(4)) + "+"
    req = report.request
    place = req.place.name if req.place else f"{req.latitude:.2f}, {req.longitude:.2f}"
    centre = ["", f"{caption} ({varga})", "",
              f"{req.year:04d}-{req.month:02d}-{req.day:02d}", place[:cw * 2 - 1], ""]
    out = [border]
    for r, row in enumerate(layout):
        cells = []
        for sign in row:
            if sign is None:
                cells.append(None)
                continue
            lines = _wrap(by_sign[sign], cw - 1)
            body = [SIGN_ABBR[sign].rjust(cw - 1) + " "] + [ln.ljust(cw) for ln in lines]
            body = (body + [" " * cw] * ch)[:ch]
            cells.append([c[:cw].ljust(cw) for c in body])
        for line in range(ch):
            parts = []
            for c, cell in enumerate(cells):
                if cell is None:
                    if c == 1:  # the merged centre spans two cells
                        i = (r - 1) * ch + line
                        text = centre[i] if 0 <= i < len(centre) else ""
                        parts.append(text.center(cw * 2 + 1))
                    continue
                parts.append(cell[line])
            out.append("|" + "|".join(parts) + "|")
        if r in (0, 2):
            out.append(border)
        elif r == 1:
            out.append("+" + "-" * cw + "+" + " " * (cw * 2 + 1) + "+" + "-" * cw + "+")
    out.append(border)
    return out


# North Indian: houses are fixed, signs move. Label anchors as fractions of the canvas.
_NORTH_ANCHORS = {1: (0.5, 0.22), 2: (0.25, 0.09), 3: (0.1, 0.25), 4: (0.25, 0.5),
                  5: (0.1, 0.75), 6: (0.25, 0.91), 7: (0.5, 0.75), 8: (0.75, 0.91),
                  9: (0.9, 0.75), 10: (0.75, 0.5), 11: (0.9, 0.25), 12: (0.75, 0.09)}


def reference_sign(report: ChartReport, varga: str) -> tuple[int, str] | None:
    """The sign of house 1 in a North Indian chart: the Lagna's, else the Moon's in the same
    varga (Chandra lagna, with a note), else None."""
    _, lagna = placements(report, varga)
    if lagna is not None:
        return lagna, ""
    pos, var = report.get("positions"), report.get("vargas")
    if varga == "D1":
        moon_f = pos.fact("sign", "graha:moon") if pos else None
    else:  # the Moon's sign in this varga, not in the Rasi chart
        moon_f = _fact(var, "varga_sign", "graha:moon", varga=varga)
    if moon_f is None or moon_f.value is None:
        return None
    return SIGNS.index(moon_f.value.split(":", 1)[1]), " (Chandra lagna)"


def north_chart(report: ChartReport, varga: str, caption: str) -> list[str]:
    """Diamond chart with house 1 at the top; counts houses anticlockwise. Without a known
    Lagna, the Moon's sign is used as house 1 (Chandra lagna) and the caption says so."""
    by_sign, _ = placements(report, varga)
    ref = reference_sign(report, varga)
    if ref is None:
        return [f"{caption} {varga}: no reference sign"]
    lagna, note = ref
    w, h = 60, 25
    grid = [[" "] * (w + 1) for _ in range(h + 1)]
    for x in range(w + 1):
        grid[0][x] = grid[h][x] = "-"
    for y in range(h + 1):
        grid[y][0] = grid[y][w] = "|"
    # one character per row keeps the shallow diagonals clean
    for y in range(1, h):
        x = round(y * w / h)
        grid[y][x] = "\\"
        grid[y][w - x] = "/"
    half = h / 2
    for y in range(1, h):
        dx = round(abs(y - half) * w / h)  # inner diamond through the edge midpoints
        if y == half:
            continue
        left, right = dx, w - dx
        grid[y][left] = "/" if y < half else "\\"
        grid[y][right] = "\\" if y < half else "/"
    for c in ((0, 0), (w, 0), (0, h), (w, h)):
        grid[c[1]][c[0]] = "+"

    def put(x: int, y: int, text: str) -> None:
        x = max(1, min(w - len(text), x - len(text) // 2))
        for i, chch in enumerate(text):
            grid[y][x + i] = chch

    for house, (fx, fy) in _NORTH_ANCHORS.items():
        sign = (lagna + house - 1) % 12
        cx, cy = round(fx * w), round(fy * h)
        put(cx, cy - 1 if house in (1, 4, 7, 10) else cy, str(sign + 1))
        lines = _wrap(by_sign[sign], 9 if house in (1, 4, 7, 10) else 7)
        if len(lines) > 3:  # the triangles are small: say what is not shown
            hidden = sum(len(ln.split()) for ln in lines[2:])
            lines = [*lines[:2], f"+{hidden} more"]
        start = cy + (0 if house in (1, 4, 7, 10) else 1)
        if house in (6, 8):
            start = cy - len(lines)
        for i, ln in enumerate(lines[:3]):
            if 0 < start + i < h:
                put(cx, start + i, ln)
    return [f"{caption} {varga}{note}", *("".join(r) for r in grid)]


# -- tables ----------------------------------------------------------------------------------
# Each table is built once as data (`*_data`) and formatted twice: as fixed-width text here
# and as a typeset table in the PDF (`astro.cli.pdf`).

@dataclass
class Table:
    header: list[str]
    rows: list[list[str]]
    widths: tuple[int | None, ...] = ()   # text column widths; None = unpadded
    right: frozenset[int] = frozenset()   # right-aligned text columns
    notes: list[str] = field(default_factory=list)


def text_rows(t: Table, header: bool = True) -> list[str]:
    def line(cells: list[str]) -> str:
        parts = []
        for i, c in enumerate(cells):
            w = t.widths[i] if i < len(t.widths) else None
            parts.append(c if w is None else (f"{c:>{w}}" if i in t.right else f"{c:<{w}}"))
        return " ".join(parts).rstrip()

    out = []
    if header:
        head = line(t.header)
        out += [head, "-" * len(head)]
    return out + [line(r) for r in t.rows]


def _fact(res: FeatureResult | None, kind: str, subject: str, **kw) -> ChartFact | None:
    if res is None:
        return None
    try:
        return res.fact(kind, subject, **kw)
    except KeyError:
        return None


def _name(subj: str) -> str:
    """'mars' → 'Ma Mars'."""
    return f"{ABBR[subj]} {title('graha:' + subj if subj != 'lagna' else 'lagna')}"


def planet_data(report: ChartReport) -> Table:
    pos, houses = report.get("positions"), report.get("houses")
    t = Table(["Body", "Sign", "Degree", "Nakshatra", "Lord", "House", "R"], [],
              (10, 12, 11, 20, 8, 5, 1), frozenset({5, 6}))
    if pos is None:
        t.notes.append("positions unavailable")
        return t
    for subj in ("lagna", *BODIES):
        s = f"graha:{subj}" if subj != "lagna" else "lagna"
        sign = _fact(pos, "sign", s)
        if sign is None or sign.value is None:
            t.rows.append(["As Lagna", "unknown (birth time unknown)", "", "", "", "", ""])
            continue
        lon = _fact(pos, "longitude", s)
        nak, pada = _fact(pos, "nakshatra", s), _fact(pos, "pada", s)
        lord = _fact(pos, "nakshatra_lord", s)
        house = _fact(houses, "house", s, frame="lagna") if s != "lagna" else None
        retro = _fact(pos, "retrograde", s)
        h = "1" if s == "lagna" else ("?" if house is None or house.value is None
                                      else f"{house.value}{mark(house)}")
        rflag = "R" if retro is not None and retro.value and subj not in (
            "rahu", "ketu", "lagna") else ""
        t.rows.append([_name(subj), title(sign.value) + mark(sign),
                       to_dms(lon.value) + mark(pada),
                       f"{title(nak.value)} {pada.value}{mark(nak)}", title(lord.value), h,
                       rflag])
    return t


def planet_table(report: ChartReport) -> list[str]:
    t = planet_data(report)
    return text_rows(t) + t.notes


DIGNITY_SHORT = {"exalted": "Exalted", "moolatrikona": "Moolatrikona", "own": "Own sign",
                 "great_friend": "Great friend", "friend": "Friend", "neutral": "Neutral",
                 "enemy": "Enemy", "great_enemy": "Great enemy", "debilitated": "Debilitated"}


def _abbr(ids: tuple[str, ...] | None) -> str:
    if not ids:
        return "-"
    return " ".join(ABBR.get(i.split(":", 1)[-1], i) for i in ids)


def condition_data(report: ChartReport) -> Table | None:
    """Dignity and condition (CALC-2), aspects received and conjunctions (REL-1)."""
    cond, asp = report.get("condition"), report.get("aspects")
    if cond is None:
        return None
    t = Table(["Body", "Dignity", "Condition", "Aspected by", "Conjunct"], [],
              (10, 14, 24, 14, None))
    for b in BODIES:
        s = f"graha:{b}"
        dig = _fact(cond, "dignity", s)
        dig_txt = "-" if dig is None or dig.value is None else \
            DIGNITY_SHORT[dig.value.split(":")[1]] + mark(dig)
        flags = []
        comb = _fact(cond, "combust", s)
        if comb is not None and comb.value:
            dist = _fact(cond, "sun_distance", s)
            flags.append(f"combust {dist.value:.1f}°{mark(comb)}")
        war = _fact(cond, "graha_yuddha", s)
        if war is not None and war.value != "none":
            flags.append(f"war {'won' if war.value == 'winner' else 'lost'}{mark(war)}")
        for kind, label in (("gandanta", "gandanta"), ("rashi_sandhi", "sandhi")):
            f = _fact(cond, kind, s)
            if f is not None and f.value:
                flags.append(label + mark(f))
        by = _fact(asp, "aspected_by", s, frame="rashi")
        conj = _fact(asp, "conjunct_with", s, frame="rashi")
        t.rows.append([_name(b), dig_txt, ", ".join(flags) or "-",
                       _abbr(by.value if by else None), _abbr(conj.value if conj else None)])
    return t


def condition_table(report: ChartReport) -> list[str]:
    t = condition_data(report)
    return ["condition unavailable"] if t is None else text_rows(t)


def aspects_data(report: ChartReport) -> Table | None:
    """Graha drishti cast by each body, as signs and houses from the Lagna."""
    asp, pos = report.get("aspects"), report.get("positions")
    if asp is None or pos is None:
        return None
    lagna = _fact(pos, "sign", "lagna")
    lagna_i = None if lagna is None or lagna.value is None else \
        SIGNS.index(lagna.value.split(":")[1])
    t = Table(["Body", "Signs aspected", "Houses from the Lagna"], [])
    for b in BODIES:
        f = _fact(asp, "aspects_signs", f"graha:{b}", frame="rashi")
        if f is None or not f.value:
            t.rows.append([_name(b), "-", ""])
            continue
        idx = [SIGNS.index(v.split(":")[1]) for v in f.value]
        t.rows.append([_name(b), ", ".join(SIGN_ABBR[i] for i in idx),
                       "" if lagna_i is None else
                       ", ".join(str((i - lagna_i) % 12 + 1) for i in idx)])
    return t


def aspects_table(report: ChartReport) -> list[str]:
    t = aspects_data(report)
    if t is None:
        return ["aspects unavailable"]
    return [f"{name:<10} {signs}{'  houses ' + houses if houses else ''}"
            for name, signs, houses in t.rows]


def varga_data(report: ChartReport) -> Table | None:
    var = report.get("vargas")
    vargas = [v for v in report.request.varga_table if v != "D1"]
    if var is None or not vargas:
        return None
    t = Table(["Body", *vargas], [], (10, *(4,) * len(vargas)))
    for subj in ("lagna", *BODIES):
        s = f"graha:{subj}" if subj != "lagna" else "lagna"
        cols = []
        for v in vargas:
            vf = _fact(var, "varga_sign", s, varga=v)
            cols.append("?" if vf is None or vf.value is None
                        else SIGN_ABBR[SIGNS.index(vf.value.split(':')[1])] + mark(vf))
        t.rows.append([_name(subj), *cols])
    vot = [ABBR[b] for b in ("lagna", *BODIES)
           if (f := _fact(var, "vargottama", "lagna" if b == "lagna" else f"graha:{b}"))
           is not None and f.value]
    if vot:
        t.notes.append(f"Vargottama (same sign in D1 and D9): {' '.join(vot)}")
    return t


def varga_table(report: ChartReport) -> list[str]:
    t = varga_data(report)
    return [] if t is None else ["Varga signs", *text_rows(t), *t.notes]


BNN_COUNTS = ((1, "with"), (5, "5th"), (9, "9th"), (2, "2nd"), (12, "12th"), (7, "7th"))


def bnn_data(report: ChartReport) -> Table | None:
    links, kar = report.get("bnn_relations"), report.get("bnn_karakas")
    if links is None:
        return None
    by_source: dict[str, dict[int, list[str]]] = {}
    for r in links.relations:
        if r.kind == "bnn_link":
            label = ABBR[r.target.split(":")[1]] + ("(r)" if r.provenance.get("via")
                                                     == "retro_previous_sign" else "")
            by_source.setdefault(r.source, {}).setdefault(int(r.value), []).append(label)
    t = Table(["Body", *(name for _, name in BNN_COUNTS)], [])
    for b in BODIES:
        rows = by_source.get(f"graha:{b}", {})
        t.rows.append([_name(b), *(" ".join(rows.get(k, [])) or "-" for k, _ in BNN_COUNTS)])
    if kar is not None:
        native = _fact(kar, "native_karaka", "native", frame="bnn")
        t.notes.append("Native karaka: " + (title(native.value) if native and native.value
                                            else "give --native-gender to choose Jupiter/Venus"))
    t.notes.append("(r) = through the retrograde-in-previous-sign variant")
    return t


def bnn_table(report: ChartReport) -> list[str]:
    t = bnn_data(report)
    if t is None:
        return []
    out = ["BNN links (signs counted from each graha)"]
    names = t.header[1:]
    for name, *cells in t.rows:
        parts = [f"{n} {c}" for n, c in zip(names, cells, strict=True) if c != "-"]
        out.append(f"  {name:<10} {'; '.join(parts) or '-'}")
    return out + [f"  {n}" for n in t.notes]


def _local(report: ChartReport, iso: str | None) -> str:
    if iso is None:
        return "unknown"
    return report.to_local(datetime.fromisoformat(iso)).strftime("%Y-%m-%d %H:%M")


def panchanga_data(report: ChartReport) -> Table | None:
    """Rows: limb, value, and when it started (vara) or ends (the other limbs)."""
    pan = report.get("panchanga")
    if pan is None:
        return None
    t = Table(["Limb", "Value", "Time"], [])
    vara = _fact(pan, "vara", "panchanga:vara")
    rise = _fact(pan, "sunrise", "panchanga:sunrise")
    t.rows.append(["Vara", title(vara.value) + mark(vara),
                   f"from sunrise {_local(report, rise.value if rise else None)}"])
    paksha = _fact(pan, "paksha", "panchanga:paksha")
    for label, kind in (("Tithi", "tithi"), ("Nakshatra", "nakshatra"),
                        ("Yoga", "nitya_yoga"), ("Karana", "karana")):
        f = _fact(pan, kind, f"panchanga:{kind}")
        end = _fact(pan, "limb_end", f"panchanga:{kind}")
        extra = f" ({title(paksha.value)} paksha)" if kind == "tithi" and paksha else ""
        t.rows.append([label, title(f.value) + mark(f) + extra,
                       f"ends {_local(report, end.value if end else None)}"])
    if pan.provenance.get("unavailable"):
        t.notes.append("No sunrise on this date at this latitude: vara unknown")
    return t


def panchanga_table(report: ChartReport) -> list[str]:
    t = panchanga_data(report)
    if t is None:
        return ["panchanga unavailable"]
    vara, *limbs = t.rows
    rows = [f"{vara[0]:<10} {vara[1]:<22} ({vara[2]})"]
    rows += [f"{label:<10} {value:<36} {when}" for label, value, when in limbs]
    if t.notes:
        rows.append("Sunrise    none on this date at this latitude: vara unknown")
    return rows


@dataclass
class DashaData:
    balance: str
    periods: Table                     # mahadashas: lord, start, end, "now" marker
    current: str | None = None                     # the active chain
    current_lines: list[str] = field(default_factory=list)  # its sandhi and period lords
    lines: list[str] = field(default_factory=list)  # how far the dates shift


def dasha_data(report: ChartReport) -> DashaData | None:
    tree, act = report.get("vimshottari"), report.get("dasha_active")
    if tree is None:
        return None
    bal = tree.facts[0]
    md0 = next(p for p in tree.periods if p.level == "MD")
    d = DashaData(f"Balance at birth: {title(md0.lord)} {bal.value:.2f} years{mark(bal)}",
                  Table(["Mahadasha", "Starts", "Ends", ""], []))
    birth = report.normalization.utc
    for p in tree.periods:
        # a span in days, not a calendar year: 29 February + 120 years may not exist
        if p.level == "MD" and birth is not None and p.end_utc > birth and \
                p.start_utc < birth + timedelta(days=120 * 365.2425):
            current = act is not None and act.periods and act.periods[0].id == p.id
            d.periods.rows.append([title(p.lord), f"{report.to_local(p.start_utc):%Y-%m-%d}",
                                   f"{report.to_local(p.end_utc):%Y-%m-%d}",
                                   "now" if current else ""])
    if act is not None and act.periods:
        chain = " / ".join(title(p.lord) for p in act.periods)
        last = act.periods[-1]
        d.current = (f"Current ({report.as_of:%Y-%m-%d}): {chain} until "
                     f"{report.to_local(last.end_utc):%Y-%m-%d}")
        for f in act.facts:
            if f.value:
                d.current_lines.append(f"{f.subject.rsplit(':', 1)[-1]} sandhi: boundary "
                               f"{f.provenance['boundary_utc'][:10]} "
                               f"({f.provenance['distance_days']:.0f} days away)")
        d.current_lines += _period_lords(report)
    early, late = md0.boundary_margin_days
    if early is not None and late is not None:
        d.lines.append(f"Dasha dates shift by {early:+.1f} / {late:+.1f} days if birth was "
                       f"{report.normalization.birth.uncertainty_minutes:g} min earlier / later")
    elif early is not None or late is not None:
        d.lines.append("The Moon changes nakshatra within the birth-time uncertainty: the whole "
                       "dasha sequence is uncertain")
    return d


def dasha_table(report: ChartReport) -> list[str]:
    d = dasha_data(report)
    if d is None:
        return ["dasha unavailable"]
    out = [d.balance]
    out += [f"  {lord:<8} {start} → {end}{'   ◀ now' if now else ''}"
            for lord, start, end, now in d.periods.rows]
    if d.current:
        out.append(d.current)
    return out + [f"  {ln}" for ln in d.current_lines] + d.lines


def _period_lords(report: ChartReport) -> list[str]:
    """One line per active lord from the period-lord context (DAS-5)."""
    cx, cond, houses = report.get("dasha_context"), report.get("condition"), report.get("houses")
    if cx is None:
        return []
    out = []
    for p in cx.periods:
        subj = f"dasha:vimshottari:{p.level}"
        lord = p.lord
        rules = _fact(cx, "lord_houses", subj)
        house = _fact(houses, "house", lord, frame="lagna")
        dig = _fact(cond, "dignity", lord)
        bits = [f"in house {house.value}" if house and house.value else None,
                ("rules " + ", ".join(h.split(":")[1] for h in rules.value))
                if rules and rules.value else None,
                DIGNITY_SHORT[dig.value.split(":")[1]].lower() if dig and dig.value else None]
        rel = _fact(cx, "from_md_lord", subj)
        if rel is not None:
            bits.append(f"{rel.value} from the MD lord")
        out.append(f"{p.level} {title(lord):<8} " + "; ".join(b for b in bits if b))
    return out


def header_fields(report: ChartReport) -> list[tuple[str, str]]:
    req, n = report.request, report.normalization
    place = req.place.label if req.place else "coordinates"
    off = n.provenance.get("offset", {})
    zone = off.get("zone") or format_offset(off.get("minutes", 0))
    when = (f"{req.year:04d}-{req.month:02d}-{req.day:02d} "
            f"{req.local_time.strftime('%H:%M') if req.local_time else '(time unknown)'}")
    method = report.method
    default = " (default)" if req.method == "parashari" and not req.method_given else ""
    fields = [
        ("Method", f"{method.id}{default}: {method.description}"
         + (" [draft: calculations only, no reviewed rules yet]" if method.status == "draft"
            else "")),
        ("Birth", f"{when} {zone} ({req.calendar})   UTC {n.utc:%Y-%m-%d %H:%M}"),
        ("Place", f"{place}  {abs(req.latitude):.4f}{'N' if req.latitude >= 0 else 'S'} "
                  f"{abs(req.longitude):.4f}{'E' if req.longitude >= 0 else 'W'}"),
        ("Profile", f"{report.profile.id}: {report.profile.ayanamsa.id} ayanamsa, "
                    f"{report.profile.house_system.replace('_', ' ')} houses, "
                    f"{report.profile.nodes.model} node"),
    ]
    pos = report.get("positions")
    if pos is not None:
        aya = next(f for f in pos.facts if f.kind == "ayanamsa")
        fields.append(("Ayanamsa", f"{aya.value:.4f}°   uncertainty ±"
                                   f"{n.birth.uncertainty_minutes:g} min"))
    return fields


def header(report: ChartReport) -> list[str]:
    return [f"{k:<10} {v}" for k, v in header_fields(report)]


def note_items(report: ChartReport) -> list[str]:
    out = list(report.normalization.assumptions)
    if report.profile.provisional:
        out.append("provisional settings awaiting expert review: "
                   + ", ".join(report.profile.provisional))
    for name, r in report.results.items():
        if r.status.value != "ok":
            out.append(f"{name}: {r.status.value} ({r.reason.value if r.reason else ''}) "
                       f"{r.detail[:120]}")
        elif r.reason is not None:  # computed, but part of it is unavailable
            out.append(f"{name}: partly {r.reason.value}: {r.detail[:120]}")
    out.append("* = changes within the birth-time uncertainty; ? = unknown")
    return out


def notes(report: ChartReport) -> list[str]:
    return [f"- {n}" for n in note_items(report)]


VARGA_NAMES = {"D1": "Rasi", "D2": "Hora", "D3": "Drekkana", "D4": "Chaturthamsa",
               "D7": "Saptamsa", "D9": "Navamsa", "D10": "Dasamsa", "D12": "Dwadasamsa",
               "D16": "Shodasamsa", "D20": "Vimsamsa", "D24": "Chaturvimsamsa",
               "D27": "Bhamsa", "D30": "Trimsamsa", "D40": "Khavedamsa", "D45": "Akshavedamsa",
               "D60": "Shashtiamsa"}

STYLES = ("north", "south")   # north (the diamond) is the default


def render(report: ChartReport, style: str = "north") -> str:
    chart = south_chart if style == "south" else north_chart
    blocks: list[list[str]] = [header(report)]
    for v in report.request.vargas:
        blocks.append(chart(report, v, VARGA_NAMES.get(v, v)))
    blocks += [planet_table(report), ["Dignity and condition"] + condition_table(report),
               ["Aspects cast (graha drishti)"] + aspects_table(report), varga_table(report),
               bnn_table(report), ["Panchanga at birth"] + panchanga_table(report),
               ["Vimshottari dasha"] + dasha_table(report), ["Notes"] + notes(report)]
    return "\n\n".join("\n".join(b) for b in blocks if b) + "\n"
