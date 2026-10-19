"""PDF report (E1–E3): chart geometry, text the font can draw, CLI behaviour, contents."""

from datetime import UTC, datetime, time
from itertools import combinations

import pytest
from pypdf import PdfReader

from astro.cli import pdf
from astro.cli.main import EXIT_ERROR, EXIT_OK, main, pdf_name
from astro.cli.report import ChartRequest, build
from astro.normalize.gazetteer import Place

AS_OF = ["--as-of", "2026-10-19T00:00+00:00"]
PUNE = ["chart", "--date", "1985-03-14", "--time", "06:42", "--place", "Pune, IN", *AS_OF]
SIZE = (pdf.FRAME_W - 22) / 2 - 2  # the size the report draws charts at
# the widest labels a chart can carry: every body retrograde (impossible, but widest) and
# sensitive
WORST = ["As*", *(f"{b}(R)*" for b in ("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa")), "Ra*", "Ke*"]


def run(*argv):
    out, err = [], []
    code = main(list(argv), out.append, err.append)
    return code, "\n".join(out), "\n".join(err)


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def inside(poly, x, y, tol=0.01):
    """Point in a convex polygon given anticlockwise or clockwise."""
    sign = 0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(cross) <= tol * ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5:
            continue
        s = 1 if cross > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_drawing(d):
    assert not d.overflow
    for h in d.houses:
        boxes = [t.box() for t in h.labels] + ([h.marker.box()] if h.marker else [])
        for x0, y0, x1, y1 in boxes:
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                assert inside(h.polygon, x, y), (h.number, x, y)
        for a, b in combinations(boxes, 2):
            assert not overlap(a, b), (h.number, a, b)


# -- geometry ---------------------------------------------------------------------------------

@pytest.mark.parametrize("sign", range(12))
def test_north_fits_every_body_in_any_house(sign):
    by_sign = {i: (WORST if i == sign else []) for i in range(12)}
    d = pdf.north_layout(by_sign, lagna=0, size=SIZE)
    check_drawing(d)
    assert sum(len(h.labels) for h in d.houses) == len(WORST)


@pytest.mark.parametrize("sign", range(12))
def test_south_fits_every_body_in_any_sign(sign):
    by_sign = {i: (WORST if i == sign else []) for i in range(12)}
    d = pdf.south_layout(by_sign, lagna=sign, size=SIZE, centre=["Rasi (D1)", "x", "y"])
    check_drawing(d)
    assert sum(len(h.labels) for h in d.houses) == len(WORST)
    for t in d.centre:  # the centre text stays in the middle 2×2 block
        x0, y0, x1, y1 = t.box()
        assert x0 >= SIZE / 4 and x1 <= 3 * SIZE / 4 and y0 >= SIZE / 4 and y1 <= 3 * SIZE / 4


def test_north_houses_run_anticlockwise_from_the_lagna():
    d = pdf.north_layout({i: [] for i in range(12)}, lagna=10, size=SIZE)
    signs = {h.number: h.sign for h in d.houses}
    assert signs[1] == 10 and signs[2] == 11 and signs[3] == 0 and signs[12] == 9
    assert [h.number for h in d.houses if h.is_lagna] == [1]
    # house 2 is up and to the left of house 1, house 12 up and to the right
    cx = {h.number: pdf._centroid(h.polygon)[0] for h in d.houses}
    assert cx[2] < cx[1] < cx[12]
    # the houses tile the square: their areas add up to it
    area = 0.0
    for h in d.houses:
        p = h.polygon
        area += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(p, p[1:] + p[:1],
                                                                         strict=True))) / 2
    assert area == pytest.approx(SIZE * SIZE)


def test_labels_that_cannot_fit_are_reported_not_dropped():
    tiny = pdf.north_layout({i: (WORST if i == 0 else []) for i in range(12)}, 0, size=40)
    assert tiny.overflow == WORST


# -- text the embedded font can draw ------------------------------------------------------------

def test_clean_keeps_what_the_font_has_and_replaces_the_rest():
    assert pdf.clean("28°01′34″") == "28°01'34\""
    assert pdf.clean("1983 → 1990") == "1983 – 1990"
    assert pdf.clean("Kraków, São Paulo, Zürich") == "Kraków, São Paulo, Zürich"
    assert pdf.clean("Łódź") == "Łódz"  # Vera has Ł and ó but not ź: only its accent goes
    assert pdf.clean("東京") == "??"
    from reportlab.pdfbase import pdfmetrics
    cmap = pdfmetrics.getFont(pdf.FONT).face.charToGlyph
    assert all(ord(c) in cmap for c in pdf.clean("ṛṣ ā ī ū ṅ ñ ṭ ḍ ṇ ś ṃ ḥ ◀ ★ …"))


# -- CLI ----------------------------------------------------------------------------------------

def pdf_text(path):
    return "\n".join(p.extract_text() for p in PdfReader(path).pages)


def test_chart_writes_a_pdf_by_default(tmp_path):
    code, out, err = run(*PUNE)
    assert code == EXIT_OK, err
    path = tmp_path / "chart-1985-03-14-0642-pune.pdf"
    assert f"PDF written to {path}" in err and path.is_file()
    assert "Rasi D1" in out  # the terminal shows the diamond by default
    reader = PdfReader(path)
    assert len(reader.pages) >= 2 and reader.metadata.title == "Natal chart 1985-03-14"
    text = pdf_text(path)
    for expected in ("Natal chart", "Rasi (D1)", "Navamsa (D9)", "Dasamsa (D10)",
                     "Pune, Maharashtra, India", "28°01'34\"", "Purva Bhadrapada 3",
                     "Dignity and condition", "Moolatrikona", "Panchanga at birth",
                     "Wednesday", "Current (2026-10-19): Mars / Rahu / Rahu", "GeoNames",
                     "provisional settings", "page 1"):
        assert expected in text, expected
    assert not list(tmp_path.glob("*.part"))


def test_pdf_options(tmp_path):
    code, _, err = run(*PUNE, "--no-pdf", "--vargas", "D1")
    assert code == EXIT_OK and "PDF" not in err and not list(tmp_path.glob("*.pdf"))
    code, out, err = run(*PUNE, "--json", "--vargas", "D1")
    assert code == EXIT_OK and out.startswith("{") and not list(tmp_path.glob("*.pdf"))
    code, _, _ = run(*PUNE, "--json", "--vargas", "D1", "--pdf", "x.pdf")
    assert code == EXIT_OK and (tmp_path / "x.pdf").is_file()
    (tmp_path / "out").mkdir()
    code, _, _ = run(*PUNE, "--vargas", "D1", "--pdf", "out")
    assert code == EXIT_OK and (tmp_path / "out" / "chart-1985-03-14-0642-pune.pdf").is_file()
    code, _, err = run(*PUNE, "--vargas", "D1", "--pdf", "nofolder/")  # a folder, not a file
    assert code == EXIT_ERROR and "PDF not written" in err and not (tmp_path / "nofolder").exists()
    with pytest.raises(SystemExit):
        run(*PUNE, "--pdf", "y.pdf", "--no-pdf")


def test_unwritable_pdf_is_an_error_after_the_report(tmp_path):
    code, out, err = run(*PUNE, "--vargas", "D1", "--pdf", str(tmp_path / "missing" / "a.pdf"))
    assert code == EXIT_ERROR and "PDF not written" in err
    assert "Rasi D1" in out  # the terminal report was still printed


def test_south_and_unknown_time_pdfs(tmp_path):
    code, _, _ = run(*PUNE, "--style", "south", "--pdf", "s.pdf")
    assert code == EXIT_OK and "Rasi (D1)" in pdf_text(tmp_path / "s.pdf")
    code, _, _ = run("chart", "--date", "1985-03-14", "--place", "Pune", *AS_OF,
                     "--method", "bnn", "--varga-table", "all", "--pdf", "u.pdf")
    text = pdf_text(tmp_path / "u.pdf")
    assert code == EXIT_OK and "Chandra lagna" in text and "time unknown" in text
    assert "BNN links" in text and "D60" in text


def test_pdf_bytes_depend_only_on_the_chart(tmp_path):
    rep = build(ChartRequest(1985, 3, 14, time(6, 42), 18.52, 73.85, timezone="Asia/Kolkata",
                             as_of=datetime(2026, 10, 19, tzinfo=UTC)))
    a = pdf.write_pdf(rep, tmp_path / "a.pdf").read_bytes()
    b = pdf.write_pdf(rep, tmp_path / "b.pdf").read_bytes()
    assert a == b and a.startswith(b"%PDF")


def test_every_chart_in_a_real_report_fits():
    rep = build(ChartRequest(1985, 3, 14, time(6, 42), 18.52, 73.85, timezone="Asia/Kolkata",
                             as_of=datetime(2026, 10, 19, tzinfo=UTC),
                             vargas=("D1", "D9", "D60")))
    for style in ("north", "south"):
        for v in ("D1", "D9", "D60"):
            d, _ = pdf.chart_drawing(rep, v, style, SIZE)
            check_drawing(d)


def test_pdf_names():
    def req(**kw):
        base = dict(year=1985, month=3, day=14, local_time=time(6, 42), latitude=-23.55,
                    longitude=-46.63)
        return ChartRequest(**{**base, **kw})

    sp = Place("São Paulo", "Sao Paulo", "BR", "Brazil", -23.55, -46.63, 0)
    assert pdf_name(req(place=sp)) == "chart-1985-03-14-0642-sao-paulo.pdf"
    assert pdf_name(req(local_time=None)) == "chart-1985-03-14-notime-23.55s46.63w.pdf"
    tokyo = Place("東京", "", "JP", "Japan", 35.68, 139.69, 0)
    assert pdf_name(req(place=tokyo)).endswith("-0642-place.pdf")
