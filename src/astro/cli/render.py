"""Plain-text rendering of a chart report: South and North Indian charts, tables."""

from __future__ import annotations

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


def north_chart(report: ChartReport, varga: str, caption: str) -> list[str]:
    """Diamond chart with house 1 at the top; counts houses anticlockwise. Without a known
    Lagna, the Moon's sign is used as house 1 (Chandra lagna) and the caption says so."""
    by_sign, lagna = placements(report, varga)
    note = ""
    if lagna is None:
        pos, var = report.get("positions"), report.get("vargas")
        if varga == "D1":
            moon_f = pos.fact("sign", "graha:moon") if pos else None
        else:  # the Moon's sign in this varga, not in the Rasi chart
            moon_f = _fact(var, "varga_sign", "graha:moon", varga=varga)
        if moon_f is None or moon_f.value is None:
            return [f"{caption} {varga}: no reference sign"]
        lagna = SIGNS.index(moon_f.value.split(":", 1)[1])
        note = " (Chandra lagna)"
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

def _fact(res: FeatureResult | None, kind: str, subject: str, **kw) -> ChartFact | None:
    if res is None:
        return None
    try:
        return res.fact(kind, subject, **kw)
    except KeyError:
        return None


def planet_table(report: ChartReport) -> list[str]:
    pos, houses, var = report.get("positions"), report.get("houses"), report.get("vargas")
    vargas = [v for v in report.request.vargas if v != "D1"]
    head = (f"{'Body':<10} {'Sign':<12} {'Degree':<11} {'Nakshatra':<20} {'Lord':<8} "
            f"{'House':>5} {'R':>1}  " + " ".join(f"{v:<4}" for v in vargas))
    out = [head, "-" * len(head)]
    if pos is None:
        return out + ["positions unavailable"]
    for subj in ("lagna", *BODIES):
        s = f"graha:{subj}" if subj != "lagna" else "lagna"
        sign = _fact(pos, "sign", s)
        if sign is None or sign.value is None:
            out.append(f"{'As Lagna':<10} unknown (birth time unknown)")
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
        vcols = []
        for v in vargas:
            vf = _fact(var, "varga_sign", s, varga=v)
            vcols.append("?" if vf is None or vf.value is None
                         else SIGN_ABBR[SIGNS.index(vf.value.split(':')[1])] + mark(vf))
        out.append(
            f"{ABBR[subj] + ' ' + title(s):<10} {title(sign.value) + mark(sign):<12} "
            f"{to_dms(lon.value) + mark(pada):<11} "
            f"{(title(nak.value) + ' ' + str(pada.value)) + mark(nak):<20} "
            f"{title(lord.value):<8} {h:>5} {rflag:>1}  " + " ".join(f"{c:<4}" for c in vcols))
    return out


def _local(report: ChartReport, iso: str | None) -> str:
    if iso is None:
        return "unknown"
    return report.to_local(datetime.fromisoformat(iso)).strftime("%Y-%m-%d %H:%M")


def panchanga_table(report: ChartReport) -> list[str]:
    pan = report.get("panchanga")
    if pan is None:
        return ["panchanga unavailable"]
    rows = []
    vara = _fact(pan, "vara", "panchanga:vara")
    rise = _fact(pan, "sunrise", "panchanga:sunrise")
    rows.append(f"Vara       {title(vara.value) + mark(vara):<22} (from sunrise "
                f"{_local(report, rise.value if rise else None)})")
    paksha = _fact(pan, "paksha", "panchanga:paksha")
    for label, kind in (("Tithi", "tithi"), ("Nakshatra", "nakshatra"),
                        ("Yoga", "nitya_yoga"), ("Karana", "karana")):
        f = _fact(pan, kind, f"panchanga:{kind}")
        end = _fact(pan, "limb_end", f"panchanga:{kind}")
        extra = f" ({title(paksha.value)} paksha)" if kind == "tithi" and paksha else ""
        rows.append(f"{label:<10} {title(f.value) + mark(f) + extra:<36} ends "
                    f"{_local(report, end.value if end else None)}")
    if pan.provenance.get("unavailable"):
        rows.append("Sunrise    none on this date at this latitude: vara unknown")
    return rows


def dasha_table(report: ChartReport) -> list[str]:
    tree, act = report.get("vimshottari"), report.get("dasha_active")
    if tree is None:
        return ["dasha unavailable"]
    bal = tree.facts[0]
    md0 = next(p for p in tree.periods if p.level == "MD")
    out = [f"Balance at birth: {title(md0.lord)} {bal.value:.2f} years{mark(bal)}"]
    birth = report.normalization.utc
    for p in tree.periods:
        # a span in days, not a calendar year: 29 February + 120 years may not exist
        if p.level == "MD" and birth is not None and p.end_utc > birth and \
                p.start_utc < birth + timedelta(days=120 * 365.2425):
            current = act is not None and act.periods and act.periods[0].id == p.id
            out.append(f"  {title(p.lord):<8} {report.to_local(p.start_utc):%Y-%m-%d} → "
                       f"{report.to_local(p.end_utc):%Y-%m-%d}{'   ◀ now' if current else ''}")
    if act is not None and act.periods:
        chain = " / ".join(title(p.lord) for p in act.periods)
        last = act.periods[-1]
        out.append(f"Current ({report.as_of:%Y-%m-%d}): {chain} until "
                   f"{report.to_local(last.end_utc):%Y-%m-%d}")
        for f in act.facts:
            if f.value:
                out.append(f"  {f.subject.rsplit(':', 1)[-1]} sandhi: boundary "
                           f"{f.provenance['boundary_utc'][:10]} "
                           f"({f.provenance['distance_days']:.0f} days away)")
    early, late = md0.boundary_margin_days
    if early is not None and late is not None:
        out.append(f"Dasha dates shift by {early:+.1f} / {late:+.1f} days if birth was "
                   f"{report.normalization.birth.uncertainty_minutes:g} min earlier / later")
    elif early is not None or late is not None:
        out.append("The Moon changes nakshatra within the birth-time uncertainty: the whole "
                   "dasha sequence is uncertain")
    return out


def header(report: ChartReport) -> list[str]:
    req, n = report.request, report.normalization
    place = req.place.label if req.place else "coordinates"
    off = n.provenance.get("offset", {})
    zone = off.get("zone") or format_offset(off.get("minutes", 0))
    when = (f"{req.year:04d}-{req.month:02d}-{req.day:02d} "
            f"{req.local_time.strftime('%H:%M') if req.local_time else '(time unknown)'}")
    lines = [
        f"Birth      {when} {zone} ({req.calendar})   UTC {n.utc:%Y-%m-%d %H:%M}",
        f"Place      {place}  {abs(req.latitude):.4f}{'N' if req.latitude >= 0 else 'S'} "
        f"{abs(req.longitude):.4f}{'E' if req.longitude >= 0 else 'W'}",
        f"Profile    {report.profile.id}: {report.profile.ayanamsa.id} ayanamsa, "
        f"{report.profile.house_system.replace('_', ' ')} houses, "
        f"{report.profile.nodes.model} node",
    ]
    pos = report.get("positions")
    if pos is not None:
        aya = next(f for f in pos.facts if f.kind == "ayanamsa")
        lines.append(f"Ayanamsa   {aya.value:.4f}°   uncertainty ±"
                     f"{n.birth.uncertainty_minutes:g} min")
    return lines


def notes(report: ChartReport) -> list[str]:
    out = []
    for a in report.normalization.assumptions:
        out.append(f"- {a}")
    if report.profile.provisional:
        out.append("- provisional settings awaiting expert review: "
                   + ", ".join(report.profile.provisional))
    for name, r in report.results.items():
        if r.status.value != "ok":
            out.append(f"- {name}: {r.status.value} ({r.reason.value if r.reason else ''}) "
                       f"{r.detail[:120]}")
    out.append("- * = changes within the birth-time uncertainty; ? = unknown")
    return out


def render(report: ChartReport, style: str = "south") -> str:
    chart = south_chart if style == "south" else north_chart
    blocks: list[list[str]] = [header(report)]
    for v in report.request.vargas:
        caption = {"D1": "Rasi", "D9": "Navamsa", "D10": "Dasamsa"}.get(v, v)
        blocks.append(chart(report, v, caption))
    blocks += [planet_table(report), ["Panchanga at birth"] + panchanga_table(report),
               ["Vimshottari dasha"] + dasha_table(report), ["Notes"] + notes(report)]
    return "\n\n".join("\n".join(b) for b in blocks) + "\n"
