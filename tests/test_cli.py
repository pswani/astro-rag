import json
import subprocess
import sys
from pathlib import Path

import pytest

from astro.cli.main import EXIT_NEEDS_INPUT, EXIT_OK, EXIT_UNSUPPORTED, main
from astro.normalize.gazetteer import CityTable, fold
from astro.resources import ResourceError, astro_home

ROOT = Path(__file__).resolve().parents[1]
AS_OF = ["--as-of", "2026-10-19T00:00+00:00"]
PUNE = ["chart", "--date", "1985-03-14", "--time", "06:42", "--place", "Pune, IN", *AS_OF]


def run(*argv):
    out, err = [], []
    code = main(list(argv), out.append, err.append)
    return code, "\n".join(out), "\n".join(err)


@pytest.fixture(scope="module")
def gaz():
    return CityTable()


# -- gazetteer ---------------------------------------------------------------------------------

def test_fold():
    assert fold("  São-Paulo ") == "sao paulo"


def test_lookup_rules(gaz):
    assert gaz.lookup("Pune").place.country_code == "IN"
    amb = gaz.lookup("Springfield")
    assert amb.status == "ambiguous" and len(amb.candidates) > 3
    # population orders the candidates but does not pick one
    pops = [p.population for p in amb.candidates]
    assert pops == sorted(pops, reverse=True)
    assert gaz.lookup("Springfield, Illinois").place.state == "Illinois"
    assert gaz.lookup("London, United Kingdom").place.country_code == "GB"
    assert gaz.lookup("sao paulo, br").place.name == "São Paulo"
    miss = gaz.lookup("Chenai")
    assert miss.status == "not_found" and miss.suggestions[0].startswith("Chennai")
    assert gaz.lookup("Springfield, FR").status == "not_found"
    assert gaz.lookup(" , ").status == "not_found"
    with pytest.raises(ValueError):
        _ = amb.place


# -- chart -------------------------------------------------------------------------------------

def test_south_chart_report():
    code, out, err = run(*PUNE)
    assert code == EXIT_OK, err
    assert "Rasi (D1)" in out and "Navamsa (D9)" in out and "Dasamsa (D10)" in out
    assert "Pune, Maharashtra, India" in out
    assert "As Lagna   Aquarius" in out and "28°01′34″" in out
    assert "Vara       Wednesday" in out  # born five minutes before sunrise
    assert "Current (2026-10-19): Mars / Rahu / Rahu" in out
    assert "provisional settings" in out and "GeoNames" in out


def test_chart_grids_are_rectangular():
    for style in ("south", "north"):
        code, out, _ = run(*PUNE, "--style", style, "--vargas", "D1")
        assert code == EXIT_OK
        grid = [ln for ln in out.splitlines() if ln and ln[0] in "+|"]
        assert grid and len({len(ln) for ln in grid}) == 1, style


def test_north_chart_has_lagna_sign_in_house_one():
    code, out, _ = run(*PUNE, "--style", "north", "--vargas", "D1")
    lines = out.splitlines()
    top = next(i for i, ln in enumerate(lines) if ln.startswith("Rasi D1"))
    house1 = "\n".join(lines[top + 4:top + 9])
    assert " 11 " in house1 and "As Su" in house1  # Aquarius rises


def test_unknown_time_uses_chandra_lagna():
    code, out, _ = run("chart", "--date", "1985-03-14", "--place", "Pune", "--style", "north",
                       *AS_OF)
    assert code == EXIT_OK
    assert "(Chandra lagna)" in out and "unknown (birth time unknown)" in out
    assert "Aquarius*" in out  # the Sun changes sign within the day


def test_coordinates_and_zone_lookup():
    code, out, err = run("chart", "--date", "1990-07-15", "--time", "04:10", "--lat", "-33.87",
                         "--lon", "151.21", "--vargas", "D1", *AS_OF)
    assert code == EXIT_OK, err
    assert "Australia/Sydney" in out and "UTC 1990-07-14 18:10" in out


def test_ambiguous_and_unknown_places_ask():
    code, _, err = run("chart", "--date", "1990-07-15", "--time", "04:10", "--place",
                       "Springfield")
    assert code == EXIT_NEEDS_INPUT and '--place "Springfield, Illinois, US"' in err
    code, _, err = run("chart", "--date", "1990-07-15", "--place", "Chenai")
    assert code == EXIT_NEEDS_INPUT and "Chennai, Tamil Nadu, India" in err
    code, _, err = run("chart", "--date", "1990-07-15", "--lat", "10")
    assert code == EXIT_NEEDS_INPUT
    code, _, err = run("chart", "--date", "1990-07-15")
    assert code == EXIT_NEEDS_INPUT


def test_dst_fold_hint_resolves_and_gap_is_rejected():
    fold_args = ["chart", "--date", "2021-11-07", "--time", "01:30", "--place",
                 "New York City", "--vargas", "D1", *AS_OF]
    code, _, err = run(*fold_args)
    assert code == EXIT_NEEDS_INPUT and "--utc-offset=-04:00" in err
    code, out, _ = run(*fold_args, "--utc-offset=-04:00")
    assert code == EXIT_OK and "UTC 2021-11-07 05:30" in out
    code, _, err = run("chart", "--date", "2021-03-14", "--time", "02:30", "--place",
                       "New York City")
    assert code == EXIT_NEEDS_INPUT and "DST gap" in err


def test_out_of_range_and_unsupported_calendar():
    code, out, err = run("chart", "--date", "1700-01-01", "--time", "12:00", "--place",
                         "London, GB")
    assert code == EXIT_UNSUPPORTED and "1800-01-01" in err and out == ""
    code, _, err = run("chart", "--date", "1985-03-14", "--place", "Pune", "--calendar",
                       "saka")
    assert code == EXIT_NEEDS_INPUT and "unsupported_calendar" in err


def test_historical_documented_offset():
    code, out, _ = run("chart", "--date", "1890-06-01", "--time", "06:42", "--place", "Pune",
                       "--utc-offset", "+05:53", "--vargas", "D1", *AS_OF)
    assert code == EXIT_OK and "UTC+05:53" in out


def test_json_output_and_stable_ids(monkeypatch):
    monkeypatch.setenv("ASTRO_CHART_KEY", "00" * 32)
    code, out, _ = run(*PUNE, "--json")
    assert code == EXIT_OK
    data = json.loads(out)
    assert {"positions", "houses", "relations", "friendship", "condition", "aspects", "vargas",
            "panchanga", "vimshottari", "dasha_active", "dasha_context"} <= set(data["results"])
    assert data["method"]["id"] == "parashari"
    assert data["normalization"]["provenance"]["place"]["query"] == "Pune, IN"
    assert all(r["status"] == "ok" for r in data["results"].values())
    code2, out2, _ = run(*PUNE, "--json")
    assert json.loads(out2)["chart_id"] == data["chart_id"]


def test_places_command():
    code, out, _ = run("places", "Springfield, US")
    assert code == EXIT_OK and "Illinois" in out
    code, _, err = run("places", "Xyzzyqq")
    assert code == EXIT_NEEDS_INPUT


def test_bad_arguments_exit_2():
    with pytest.raises(SystemExit) as e:
        run("chart", "--date", "1985-3-14x", "--place", "Pune")
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        run("chart", "--date", "1985-03-14", "--time", "06:42+05:30", "--place", "Pune")


def test_resources(monkeypatch, tmp_path):
    assert astro_home() == ROOT
    monkeypatch.setenv("ASTRO_HOME", str(tmp_path))
    with pytest.raises(ResourceError):
        astro_home()
    code, _, err = run("ephemeris", "path")
    assert code == 1 and "ASTRO_HOME" in err


def test_python_m_astro():
    out = subprocess.run([sys.executable, "-m", "astro", "ephemeris", "path"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip().endswith("data/ephe")


# -- review findings (C6) ----------------------------------------------------------------------

def test_feb_29_birth_renders():
    code, out, err = run("chart", "--date", "1980-02-29", "--time", "12:00", "--place",
                         "Pune, IN", "--vargas", "D1", *AS_OF)
    assert code == EXIT_OK, err
    assert "Vimshottari dasha" in out


@pytest.mark.parametrize("query,state", [("Los Angeles, CA", "California"),
                                         ("Atlanta, Georgia", "Georgia"),
                                         ("Springfield, IL", "Illinois"),
                                         ("Denver, CO", "Colorado")])
def test_state_qualifiers_that_look_like_countries(gaz, query, state):
    r = gaz.lookup(query)
    assert any(p.state == state for p in r.candidates), (query, r)


def test_exact_state_beats_prefix(gaz):
    r = gaz.lookup("Cuiabá, Mato Grosso")
    assert r.status == "found" and r.place.state == "Mato Grosso"


def test_unknown_time_varga_uses_varga_moon():
    from astro.cli.render import north_chart
    from astro.cli.report import ChartRequest, build

    rep = build(ChartRequest(1985, 3, 14, None, 18.52, 73.85, timezone="Asia/Kolkata"))
    d9 = rep.get("vargas").fact("varga_sign", "graha:moon", varga="D9").value
    sign_no = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio",
               "sagittarius", "capricorn", "aquarius", "pisces"].index(d9.split(":")[1]) + 1
    lines = north_chart(rep, "D9", "Navamsa")
    assert lines[0].endswith("(Chandra lagna)")
    assert f" {sign_no} " in "\n".join(lines[4:9])  # house 1 carries the D9 Moon's sign


def test_invalid_inputs_do_not_traceback():
    base = ["chart", "--place", "Pune", "--time", "06:42"]
    code, _, err = run(*base, "--date", "1985-13-01")
    assert code == EXIT_NEEDS_INPUT and "invalid input" in err
    code, _, err = run(*base, "--date", "1985-03-14", "--profile", "typo")
    assert code == EXIT_NEEDS_INPUT and "parashari_v1" in err
    for bad in (["--uncertainty", "1000"], ["--utc-offset=+0530"], ["--utc-offset=+05:75"]):
        with pytest.raises(SystemExit) as e:
            run(*base, "--date", "1985-03-14", *bad)
        assert e.value.code == 2


def test_missing_ephemeris_is_a_setup_error(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRO_EPHE", str(tmp_path))
    code, _, err = run(*PUNE)
    assert code == 1 and "astro ephemeris fetch" in err


def test_crowded_sign_never_drops_a_body():
    from astro.cli.render import south_chart
    from astro.cli.report import ChartRequest, build

    rep = build(ChartRequest(1985, 3, 14, None, 18.52, 73.85, timezone="Asia/Kolkata"))
    pos = rep.results["positions"]
    crowded = tuple(f.model_copy(update={"value": "rashi:aries"}) if f.kind == "sign" else f
                    for f in pos.facts)
    rep.results["positions"] = pos.model_copy(update={"facts": crowded})
    text = "\n".join(south_chart(rep, "D1", "Rasi"))
    for ab in ("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"):
        assert ab in text, ab


def test_fold_hint_mentions_tz():
    code, _, err = run("chart", "--date", "2024-10-27", "--time", "01:30", "--lat", "51.5",
                       "--lon", "-0.1", "--tz", "Europe/London")
    assert code == EXIT_NEEDS_INPUT and "in place of --tz" in err


def test_fetch_survives_network_errors(monkeypatch, tmp_path):
    import urllib.error

    from astro import ephemeris_fetch

    def boom(*a, **k):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(ephemeris_fetch.urllib.request, "urlopen", boom)
    logs = []
    ok = ephemeris_fetch.fetch([ROOT / "profiles/calc/parashari_v1.yaml"], tmp_path, logs.append)
    assert not ok and sum("failed" in s for s in logs) == 3
    assert not any(tmp_path.iterdir())


# -- D9: method, vargas, condition and aspects in the report --------------------------------

def test_default_method_is_stated_and_sections_present():
    code, out, _ = run(*PUNE)
    assert code == EXIT_OK
    assert out.startswith("Method     parashari (default):")  # INP-5
    for section in ("Dignity and condition", "Aspects cast (graha drishti)", "Varga signs"):
        assert section in out
    assert "Ve Venus   Exalted        gandanta" in out
    assert "MD Mars     in house 3; rules 3, 10; moolatrikona" in out


def test_bnn_method_and_native_gender():
    code, out, _ = run(*PUNE, "--method", "bnn", "--vargas", "D1")
    assert code == EXIT_OK and "Method     bnn:" in out and "Profile    bnn_v1" in out
    assert "BNN links" in out and "give --native-gender" in out
    code, out, _ = run(*PUNE, "--method", "bnn", "--native-gender", "female", "--vargas", "D1")
    assert "Native karaka: Venus" in out


def test_all_vargas_and_unknown_names():
    code, out, _ = run(*PUNE, "--varga-table", "all", "--vargas", "D60")
    assert code == EXIT_OK and "Shashtiamsa D60" not in out and "Shashtiamsa (D60)" in out
    assert "D2   D3   D4   D7   D9   D10  D12  D16  D20  D24  D27  D30  D40  D45  D60" in out
    code, _, err = run(*PUNE, "--vargas", "D5")
    assert code == EXIT_NEEDS_INPUT and "unknown varga D5" in err
    code, _, err = run(*PUNE, "--method", "kp")
    assert code == EXIT_NEEDS_INPUT and "unknown method" in err
    code, _, err = run(*PUNE, "--method", "parashari", "--profile", "bnn_v1")
    assert code == EXIT_UNSUPPORTED and "not a calculation profile of method parashari" in err


def test_vargas_keeps_its_meaning_and_varga_table_is_separate():
    code, out, _ = run(*PUNE, "--vargas", "D1,D9")
    assert code == EXIT_OK and "Navamsa (D9)" in out and "Dasamsa (D10)" not in out
    assert "Body       D9" in out  # the table defaults to the charts drawn
    assert "[draft: calculations only, no reviewed rules yet]" in out


@pytest.mark.parametrize("key,message", [("xyz", "hexadecimal"), ("00ff", "at least 32")])
def test_invalid_chart_key_is_a_setup_error(monkeypatch, key, message):
    monkeypatch.setenv("ASTRO_CHART_KEY", key)
    code, _, err = run(*PUNE)
    assert code == 1 and message in err
