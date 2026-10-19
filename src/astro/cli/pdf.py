"""PDF chart report: the terminal report's content, typeset, with the charts drawn as vectors.

The charts are laid out as data first (`north_layout`, `south_layout`): polygons, lines and
text items in points. Text is fitted inside each house so nothing overlaps or leaves its house,
which the tests check geometrically. reportlab only paints the result.

Fonts: Bitstream Vera, which ships with reportlab, is embedded so the file looks the same
everywhere. Characters Vera lacks are replaced (′ → ', → → –) rather than drawn as boxes.
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus import Table as RLTable

from astro.cli.render import (
    SIGN_ABBR,
    VARGA_NAMES,
    Table,
    aspects_data,
    bnn_data,
    condition_data,
    dasha_data,
    header_fields,
    note_items,
    panchanga_data,
    placements,
    planet_data,
    reference_sign,
    varga_data,
)
from astro.cli.report import ChartReport
from astro.normalize.gazetteer import ATTRIBUTION

FONT, BOLD = "AstroSans", "AstroSans-Bold"
_FONT_DIR = Path(reportlab.__file__).parent / "fonts"

INK = colors.HexColor("#1f2a44")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#c7cdd8")
LAGNA_FILL = colors.HexColor("#fbf3dc")
HEAD_FILL = colors.HexColor("#e8ecf3")
ZEBRA = colors.HexColor("#f6f7fa")

PAGE_W, PAGE_H = A4
MARGIN = 40.0
FRAME_W = PAGE_W - 2 * MARGIN


def register_fonts() -> None:
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, str(_FONT_DIR / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont(BOLD, str(_FONT_DIR / "VeraBd.ttf")))


_REPLACE = {"′": "'", "″": '"', "→": "–", "◀": "<", "★": "*", "−": "-", "…": "..."}


def clean(text: str) -> str:
    """Text the embedded font can draw: replacements for the few symbols it lacks, accents
    dropped from letters it lacks, and '?' for anything else."""
    register_fonts()
    cmap = pdfmetrics.getFont(FONT).face.charToGlyph
    out = []
    for ch in text:
        if ord(ch) in cmap or ch in "\n\t":
            out.append(ch)
        elif ch in _REPLACE:
            out.append(_REPLACE[ch])
        else:
            base = "".join(c for c in unicodedata.normalize("NFKD", ch)
                           if not unicodedata.combining(c) and ord(c) in cmap)
            out.append(base or "?")
    return "".join(out)


def width(text: str, size: float, bold: bool = False) -> float:
    register_fonts()
    return pdfmetrics.stringWidth(text, BOLD if bold else FONT, size)


# -- chart geometry ---------------------------------------------------------------------------

Point = tuple[float, float]


@dataclass(frozen=True)
class TextItem:
    text: str
    x: float          # left edge
    y: float          # baseline
    size: float
    bold: bool = False
    color: str = "ink"

    def box(self) -> tuple[float, float, float, float]:
        """(x0, y0, x1, y1) covering the glyphs: descenders to cap height."""
        return (self.x, self.y - 0.22 * self.size,
                self.x + width(self.text, self.size, self.bold), self.y + 0.76 * self.size)


@dataclass
class House:
    number: int                 # 1–12 (north) or the sign index + 1 (south)
    polygon: list[Point]
    sign: int
    labels: list[TextItem] = field(default_factory=list)
    marker: TextItem | None = None   # the sign number (north) or name (south)
    is_lagna: bool = False


@dataclass
class ChartDrawing:
    size: float
    lines: list[tuple[Point, Point]]
    houses: list[House]
    centre: list[TextItem] = field(default_factory=list)
    overflow: list[str] = field(default_factory=list)  # labels that could not be fitted


SIZES = (9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5, 5.0)


def _span(poly: list[Point], y: float) -> tuple[float, float] | None:
    """x-range of a convex polygon at height y."""
    xs = []
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if y1 == y2:
            if y == y1:
                xs += [x1, x2]
            continue
        if min(y1, y2) <= y <= max(y1, y2):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return (min(xs), max(xs)) if xs else None


def _band(poly: list[Point], lo: float, hi: float,
          blocked: list[tuple[float, float, float, float]]) -> tuple[float, float] | None:
    """The widest x-interval where a line of text occupying [lo, hi] stays inside the convex
    polygon and clear of the blocked boxes."""
    a, b = _span(poly, lo), _span(poly, hi)
    if a is None or b is None:
        return None
    # the polygon is convex, so the band is narrowest at one of its two ends
    x0, x1 = max(a[0], b[0]), min(a[1], b[1])
    free = [(x0, x1)] if x1 > x0 else []
    for bx0, by0, bx1, by1 in blocked:
        if by1 <= lo or by0 >= hi:
            continue
        nxt = []
        for f0, f1 in free:
            if bx0 > f0:
                nxt.append((f0, min(f1, bx0)))
            if bx1 < f1:
                nxt.append((max(f0, bx1), f1))
        free = [(f0, f1) for f0, f1 in nxt if f1 > f0]
    return max(free, key=lambda f: f[1] - f[0]) if free else None


def _shrink(poly: list[Point], pad: float) -> list[Point]:
    """The polygon pulled towards its centroid, which keeps text off the chart's lines. The
    clearance is about `pad` along the edges and more near the corners."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, y in poly:
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        k = max(0.0, (d - 2.2 * pad) / d) if d else 0.0
        out.append((cx + (x - cx) * k, cy + (y - cy) * k))
    return out


def fit_labels(poly: list[Point], labels: list[str], anchor: Point,
               blocked: Iterable[tuple[float, float, float, float]] = (),
               pad: float = 2.0) -> list[TextItem] | None:
    """Place labels in rows inside a convex polygon, largest font first, rows centred on the
    anchor height where possible. None if they do not fit even at the smallest size."""
    if not labels:
        return []
    inner = _shrink(poly, pad)
    blocked = list(blocked)
    ys = [p[1] for p in poly]
    lo_y, hi_y = min(ys), max(ys)
    for size in SIZES:
        lh = size * 1.3
        gap = width(" ", size) * 1.5
        # candidate centres: the anchor first, then stepping outwards across the polygon
        steps = [anchor[1] + k * lh / 2 for k in range(0, 40)]
        steps += [anchor[1] - k * lh / 2 for k in range(1, 40)]
        steps.sort(key=lambda c: abs(c - anchor[1]))
        for n in range(1, len(labels) + 1):
            for cy in steps:
                top = cy + n * lh / 2
                if top > hi_y or top - n * lh < lo_y:
                    continue
                items = _rows(inner, labels, n, top, lh, size, gap, blocked)
                if items is not None:
                    return items
    return None


def _rows(poly, labels, n, top, lh, size, gap, blocked) -> list[TextItem] | None:
    """n rows from `top` down, filled greedily and centred in the polygon's width at each
    row; None unless every label fits."""
    items: list[TextItem] = []
    rest = list(labels)
    for i in range(n):
        if not rest:
            break
        baseline = top - (i + 1) * lh + 0.15 * lh + 0.22 * size
        # the glyph box of a row, not the full line height, has to fit
        span = _band(poly, baseline - 0.22 * size, baseline + 0.76 * size, blocked)
        if span is None:
            return None
        avail = span[1] - span[0]
        row: list[str] = []
        used = 0.0
        while rest:
            w = width(rest[0], size)
            need = w if not row else used + gap + w
            if need > avail:
                break
            row.append(rest.pop(0))
            used = need
        if not row:
            return None
        x = (span[0] + span[1]) / 2 - used / 2
        for lab in row:
            items.append(TextItem(lab, x, baseline, size))
            x += width(lab, size) + gap
    return None if rest else items


def _scale(points: Iterable[Point], s: float) -> list[Point]:
    return [(x * s, y * s) for x, y in points]


# North Indian diamond on the unit square, y up. House 1 is the top rhombus; houses run
# anticlockwise. `apex` is the inner corner, where the sign number sits.
_C = (0.5, 0.5)
NORTH_HOUSES: dict[int, tuple[list[Point], Point]] = {
    1: ([(0.5, 1), (0.25, 0.75), _C, (0.75, 0.75)], _C),
    2: ([(0, 1), (0.5, 1), (0.25, 0.75)], (0.25, 0.75)),
    3: ([(0, 1), (0.25, 0.75), (0, 0.5)], (0.25, 0.75)),
    4: ([(0, 0.5), (0.25, 0.75), _C, (0.25, 0.25)], _C),
    5: ([(0, 0.5), (0.25, 0.25), (0, 0)], (0.25, 0.25)),
    6: ([(0, 0), (0.25, 0.25), (0.5, 0)], (0.25, 0.25)),
    7: ([(0.5, 0), (0.25, 0.25), _C, (0.75, 0.25)], _C),
    8: ([(0.5, 0), (0.75, 0.25), (1, 0)], (0.75, 0.25)),
    9: ([(1, 0), (0.75, 0.25), (1, 0.5)], (0.75, 0.25)),
    10: ([(1, 0.5), (0.75, 0.25), _C, (0.75, 0.75)], _C),
    11: ([(1, 0.5), (0.75, 0.75), (1, 1)], (0.75, 0.75)),
    12: ([(1, 1), (0.75, 0.75), (0.5, 1)], (0.75, 0.75)),
}


def _centroid(poly: list[Point]) -> Point:
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def north_layout(by_sign: dict[int, list[str]], lagna: int, size: float) -> ChartDrawing:
    lines = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (0, 0)),
             ((0, 0), (1, 1)), ((0, 1), (1, 0)), ((0.5, 1), (0, 0.5)), ((0, 0.5), (0.5, 0)),
             ((0.5, 0), (1, 0.5)), ((1, 0.5), (0.5, 1))]
    d = ChartDrawing(size, [tuple(_scale(seg, size)) for seg in lines], [])
    num_size = max(6.0, size / 34)
    for house, (unit_poly, unit_apex) in NORTH_HOUSES.items():
        poly = _scale(unit_poly, size)
        sign = (lagna + house - 1) % 12
        cx, cy = _centroid(poly)
        ax, ay = unit_apex[0] * size, unit_apex[1] * size
        # the number sits a little way from the inner corner towards the house's centre
        k = 0.3 if house in (1, 4, 7, 10) else 0.4
        nx, ny = ax + (cx - ax) * k, ay + (cy - ay) * k
        txt = str(sign + 1)
        marker = TextItem(txt, nx - width(txt, num_size) / 2, ny - 0.27 * num_size, num_size,
                          color="muted")
        h = House(house, poly, sign, marker=marker, is_lagna=house == 1)
        mx0, my0, mx1, my1 = marker.box()
        labels = fit_labels(poly, by_sign[sign], (cx, cy),
                            blocked=[(mx0 - 1, my0 - 1, mx1 + 1, my1 + 1)])
        if labels is None:
            d.overflow += by_sign[sign]
            labels = []
        h.labels = labels
        d.houses.append(h)
    return d


SOUTH_GRID = ((11, 0, 1, 2), (10, None, None, 3), (9, None, None, 4), (8, 7, 6, 5))


def south_layout(by_sign: dict[int, list[str]], lagna: int | None, size: float,
                 centre: list[str]) -> ChartDrawing:
    cell = size / 4
    d = ChartDrawing(size, [], [])
    for i in range(5):
        v = i * cell
        if i in (0, 4):
            d.lines += [((0, v), (size, v)), ((v, 0), (v, size))]
        else:  # the inner rules stop at the centre box
            d.lines += [((0, v), (cell, v)), ((size - cell, v), (size, v)),
                        ((v, 0), (v, cell)), ((v, size - cell), (v, size))]
    lo, hi = cell, size - cell  # the centre box
    d.lines += [((lo, lo), (lo, hi)), ((hi, lo), (hi, hi)), ((lo, lo), (hi, lo)),
                ((lo, hi), (hi, hi))]
    name_size = max(6.0, size / 36)
    for r, row in enumerate(SOUTH_GRID):
        for c, sign in enumerate(row):
            if sign is None:
                continue
            x0, y1 = c * cell, size - r * cell
            poly = [(x0, y1 - cell), (x0 + cell, y1 - cell), (x0 + cell, y1), (x0, y1)]
            marker = TextItem(SIGN_ABBR[sign], x0 + cell - 3 - width(SIGN_ABBR[sign], name_size),
                              y1 - 3 - 0.76 * name_size, name_size, color="muted")
            h = House(sign + 1, poly, sign, marker=marker, is_lagna=sign == lagna)
            mx0, my0, mx1, my1 = marker.box()
            labels = fit_labels(poly, by_sign[sign], (x0 + cell / 2, y1 - cell / 2 - 2),
                                blocked=[(mx0 - 1, my0 - 1, mx1 + 1, my1 + 1)])
            if labels is None:
                d.overflow += by_sign[sign]
                labels = []
            h.labels = labels
            d.houses.append(h)
    sizes = [10.0, 8.0, 8.0]
    y = size / 2 + sum(s * 1.4 for s in sizes[:len(centre)]) / 2
    for i, text in enumerate(centre):
        s = sizes[min(i, len(sizes) - 1)]
        while width(text, s, i == 0) > 2 * cell - 8 and s > 5:
            s -= 0.5
        y -= s * 1.4
        d.centre.append(TextItem(text, size / 2 - width(text, s, i == 0) / 2, y + 0.3 * s, s,
                                 bold=i == 0))
    return d


class ChartFlowable(Flowable):
    def __init__(self, drawing: ChartDrawing, caption: str, note: str = ""):
        super().__init__()
        self.drawing, self.caption, self.note = drawing, caption, note
        self.width = drawing.size
        self.height = drawing.size + 20

    def draw(self) -> None:
        c, d = self.canv, self.drawing
        c.saveState()
        c.setFillColor(INK)
        c.setFont(BOLD, 10)
        c.drawString(0, d.size + 7, clean(self.caption))
        if self.note:
            c.setFont(FONT, 8)
            c.setFillColor(MUTED)
            c.drawRightString(d.size, d.size + 7, clean(self.note))
        for h in d.houses:
            if h.is_lagna:
                p = c.beginPath()
                p.moveTo(*h.polygon[0])
                for pt in h.polygon[1:]:
                    p.lineTo(*pt)
                p.close()
                c.setFillColor(LAGNA_FILL)
                c.drawPath(p, stroke=0, fill=1)
        c.setStrokeColor(INK)
        c.setLineWidth(0.9)
        for (x0, y0), (x1, y1) in d.lines:
            c.line(x0, y0, x1, y1)
        for h in d.houses:
            for t in ([h.marker] if h.marker else []) + h.labels:
                _draw_text(c, t)
        for t in d.centre:
            _draw_text(c, t)
        if d.overflow:
            c.setFont(FONT, 7)
            c.setFillColor(MUTED)
            c.drawString(0, -9, clean("not drawn: " + " ".join(d.overflow)))
        c.restoreState()


def _draw_text(c, t: TextItem) -> None:
    c.setFont(BOLD if t.bold else FONT, t.size)
    c.setFillColor(MUTED if t.color == "muted" else INK)
    c.drawString(t.x, t.y, t.text)


def chart_drawing(report: ChartReport, varga: str, style: str,
                  size: float) -> tuple[ChartDrawing, str] | None:
    """The drawing for one varga and the caption note, or None without a reference sign."""
    by_sign, lagna = placements(report, varga)
    by_sign = {k: [clean(x) for x in v] for k, v in by_sign.items()}
    if style == "south":
        req = report.request
        place = req.place.name if req.place else f"{req.latitude:.2f}, {req.longitude:.2f}"
        centre = [f"{VARGA_NAMES.get(varga, varga)} ({varga})",
                  f"{req.year:04d}-{req.month:02d}-{req.day:02d}", clean(place)]
        return south_layout(by_sign, lagna, size, centre), ""
    ref = reference_sign(report, varga)
    if ref is None:
        return None
    sign, note = ref
    return north_layout(by_sign, sign, size), note.strip(" ()")


# -- document ---------------------------------------------------------------------------------

def _styles() -> dict[str, ParagraphStyle]:
    register_fonts()
    base = ParagraphStyle("body", fontName=FONT, fontSize=8.5, leading=11, textColor=INK,
                          alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=17, leading=21),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10, leading=13,
                                   textColor=MUTED),
        "h2": ParagraphStyle("h2", parent=base, fontName=BOLD, fontSize=11.5, leading=15,
                             spaceBefore=10, spaceAfter=4),
        "body": base,
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10),
        "head": ParagraphStyle("head", parent=base, fontName=BOLD, fontSize=8, leading=10),
        "key": ParagraphStyle("key", parent=base, fontName=BOLD, textColor=MUTED),
        "strong": ParagraphStyle("strong", parent=base, fontName=BOLD),
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5,
                                textColor=MUTED),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(text)), style)


def _col_widths(cells: list[list[str]], avail: float, size: float = 8.0) -> list[float]:
    """Natural column widths (the header row is bold), spread to fill `avail`; when the
    table is too wide, the widest columns are narrowed first and their cells wrap."""
    pad = 8.0 + 3.0  # cell padding plus a little air
    ncol = max(len(r) for r in cells)
    nat = [max((width(clean(r[i]), size, bold=k == 0) for k, r in enumerate(cells)
                if i < len(r)), default=0) + pad for i in range(ncol)]
    total = sum(nat)
    if total <= avail:
        # wide tables fill the line; narrow ones get some air but stay compact
        scale = avail / total if total >= 0.6 * avail else min(1.35, avail / total)
        return [w * scale for w in nat]
    while sum(nat) > avail + 0.01:
        wide = max(nat)
        narrower = [w for w in nat if w < wide]
        count = len(nat) - len(narrower)
        target = max((avail - sum(narrower)) / count, max(narrower, default=0))
        if target >= wide:  # every column equally wide and still too wide: share the space
            return [avail / ncol] * ncol
        nat = [target if w == wide else w for w in nat]
    return nat


def table_flowable(t: Table, st: dict[str, ParagraphStyle], avail: float = FRAME_W,
                   right: Iterable[int] = (), highlight: Iterable[int] = ()) -> RLTable:
    """A typeset table; `highlight` lists body rows (0-based) to shade and set in bold."""
    cells = [t.header, *t.rows]
    widths = _col_widths(cells, avail)
    right = set(right)

    marked = {r + 1 for r in highlight}

    def cell(text: str, i: int, row: int) -> Paragraph:
        style = st["head"] if row == 0 or row in marked else st["cell"]
        if i in right:
            style = ParagraphStyle(f"{style.name}-r", parent=style, alignment=2)
        return _p(text, style)

    data = [[cell(c, i, r) for i, c in enumerate(row)] for r, row in enumerate(cells)]
    tbl = RLTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [("BACKGROUND", (0, 0), (-1, 0), HEAD_FILL),
             ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
             ("LINEBELOW", (0, -1), (-1, -1), 0.4, RULE),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    style += [("BACKGROUND", (0, r), (-1, r), ZEBRA) for r in range(2, len(cells), 2)]
    style += [("BACKGROUND", (0, r), (-1, r), LAGNA_FILL) for r in sorted(marked)]
    tbl.setStyle(TableStyle(style))
    return tbl


def _section(title: str, body: list[Flowable], st) -> list[Flowable]:
    # a section stays on one page when it fits on a page; KeepTogether splits it otherwise
    return [CondPageBreak(60), KeepTogether([_p(title, st["h2"]), *body])]


def _charts(report: ChartReport, style: str) -> list[Flowable]:
    gap = 22.0
    size = (FRAME_W - gap) / 2 - 2
    flow: list[Flowable] = []
    st = _styles()
    for v in report.request.vargas:
        caption = f"{VARGA_NAMES.get(v, v)} ({v})"
        got = chart_drawing(report, v, style, size)
        if got is None:  # as in the terminal: say so rather than leave a gap
            flow.append(_p(f"{caption}: no reference sign", st["body"]))
            continue
        drawing, note = got
        flow.append(ChartFlowable(drawing, caption, note))
    rows = [flow[i:i + 2] for i in range(0, len(flow), 2)]
    out: list[Flowable] = []
    for row in rows:
        cells = row + [Spacer(size, 1)] * (2 - len(row))
        t = RLTable([cells], colWidths=[size + gap / 2] * 2, hAlign="LEFT")
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        out.append(t)
    return out


def story(report: ChartReport, style: str = "north") -> list[Flowable]:
    st = _styles()
    req = report.request
    when = (f"{req.year:04d}-{req.month:02d}-{req.day:02d}"
            + (f" {req.local_time:%H:%M}" if req.local_time else " (time unknown)"))
    place = req.place.label if req.place else f"{req.latitude:.4f}, {req.longitude:.4f}"
    out: list[Flowable] = [_p("Natal chart", st["title"]), _p(f"{when}  ·  {place}",
                                                             st["subtitle"]), Spacer(1, 8)]
    fields = header_fields(report)
    kv = RLTable([[_p(k, st["key"]), _p(v, st["body"])] for k, v in fields],
                 colWidths=[62, FRAME_W - 62], hAlign="LEFT")
    kv.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    out += [kv, Spacer(1, 12), *_charts(report, style)]

    def add(title: str, t: Table | None, right: Iterable[int] = (), extra: list[str] = ()):
        if t is None:
            out.extend(_section(title, [_p("unavailable", st["body"])], st))
            return
        body: list[Flowable] = [table_flowable(t, st, right=right)]
        body += [Spacer(1, 3)] + [_p(n, st["small"]) for n in [*t.notes, *extra]]
        out.extend(_section(title, body, st))

    add("Planets", planet_data(report), right=(5,))
    add("Dignity and condition", condition_data(report))
    add("Aspects cast (graha drishti)", aspects_data(report))
    if (vt := varga_data(report)) is not None:
        add("Varga signs", vt)
    if (bt := bnn_data(report)) is not None:
        add("BNN links (signs counted from each graha)", bt)
    add("Panchanga at birth", panchanga_data(report))
    d = dasha_data(report)
    if d is None:
        add("Vimshottari dasha", None)
    else:
        now = [i for i, r in enumerate(d.periods.rows) if r[-1]]
        body: list[Flowable] = [_p(d.balance, st["body"]), Spacer(1, 4),
                                table_flowable(d.periods, st, highlight=now), Spacer(1, 4)]
        if d.current:
            body.append(_p(d.current, st["strong"]))
        indent = ParagraphStyle("indent", parent=st["body"], leftIndent=10)
        body += [_p(ln, indent) for ln in d.current_lines]
        body += [_p(ln, st["body"]) for ln in d.lines]
        out.extend(_section("Vimshottari dasha", body, st))
    items = note_items(report)
    if req.place is not None:
        items.append(ATTRIBUTION)
    out.extend(_section("Notes", [_p(f"•  {n}", st["small"]) for n in items], st))
    return out
    return out


def _version() -> str:
    try:
        return metadata.version("astro")
    except metadata.PackageNotFoundError:
        return "dev"


def write_pdf(report: ChartReport, path: str | os.PathLike, style: str = "north") -> Path:
    """Write the report to `path` and return it. The bytes depend only on the report (no
    timestamps), so the same chart gives the same file."""
    register_fonts()
    path = Path(path)
    req = report.request
    title = f"Natal chart {req.year:04d}-{req.month:02d}-{req.day:02d}"
    footer = clean(f"astro {_version()}  ·  method {report.method.id}  ·  profile "
                   f"{report.profile.id}")

    def page(c, doc) -> None:
        c.saveState()
        c.setFont(FONT, 7.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, MARGIN / 2, footer)
        c.drawRightString(PAGE_W - MARGIN, MARGIN / 2, f"page {doc.page}")
        c.restoreState()

    tmp = path.with_name(path.name + ".part")
    doc = SimpleDocTemplate(str(tmp), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN, title=title,
                            author="astro", subject="Vedic natal chart", creator="astro",
                            invariant=True)
    try:
        doc.build(story(report, style), onFirstPage=page, onLaterPages=page)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path
