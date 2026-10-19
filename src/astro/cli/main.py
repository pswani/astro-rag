"""`astro` command line: natal charts from birth date, time and place.

    astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN"
    astro chart --date 1985-03-14 --lat 18.52 --lon 73.85 --tz Asia/Kolkata --style north
    astro chart --date 1985-03-14 --time 06:42 --place Pune --method bnn --varga-table all
    astro places Springfield
    astro ephemeris fetch

Exit codes: 0 ok, 2 more input needed (ambiguous place, DST fold or gap, unknown zone…),
3 unsupported (date outside the ephemeris, unknown calendar…), 1 other errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time

from pydantic import ValidationError

from astro.calc.core.status import CalcError
from astro.calc.core.timescale import utc_from_jd
from astro.cli.fmt import format_offset
from astro.normalize.gazetteer import ATTRIBUTION, Place, default_gazetteer
from astro.resources import ResourceError, astro_home, ephemeris_dir

EXIT_OK, EXIT_ERROR, EXIT_NEEDS_INPUT, EXIT_UNSUPPORTED = 0, 1, 2, 3


def _date(s: str) -> tuple[int, int, int]:
    try:
        y, m, d = (int(x) for x in s.split("-"))
    except ValueError as e:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from e
    return y, m, d


def _time(s: str) -> time:
    try:
        t = time.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("use HH:MM or HH:MM:SS (local clock time)") from e
    if t.tzinfo is not None:
        raise argparse.ArgumentTypeError("give the clock time without an offset; use --tz or "
                                         "--utc-offset")
    return t


def _offset(s: str) -> int:
    """'+05:30', '-04:00' or '+5' → minutes, within ±16 h."""
    sign = -1 if s.startswith("-") else 1
    h, colon, m = s.lstrip("+-").partition(":")
    if not h.isdigit() or len(h) > 2 or (colon and (not m.isdigit() or len(m) != 2)):
        raise argparse.ArgumentTypeError("use ±HH:MM, e.g. +05:30")
    minutes = int(h) * 60 + (int(m) if m else 0)
    if (m and int(m) >= 60) or minutes > 16 * 60:
        raise argparse.ArgumentTypeError("offset must be ±HH:MM with MM < 60, within ±16:00")
    return sign * minutes


def _uncertainty(s: str) -> float:
    try:
        v = float(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("minutes, e.g. 5") from e
    if not 0 <= v <= 720:
        raise argparse.ArgumentTypeError("between 0 and 720 minutes")
    return v


def _instant(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("use an ISO date or date-time") from e
    if dt.tzinfo is None:
        raise argparse.ArgumentTypeError("give a UTC offset, e.g. 2026-10-19T00:00+00:00")
    return dt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="astro", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("chart", help="natal chart from date, time and place of birth")
    c.add_argument("--date", type=_date, required=True, help="birth date YYYY-MM-DD")
    c.add_argument("--time", type=_time, help="local clock time HH:MM[:SS]; omit if unknown")
    c.add_argument("--calendar", default="gregorian", help="gregorian (default) or julian")
    where = c.add_argument_group("place (a name, or coordinates)")
    where.add_argument("--place", help='"City[, State][, Country]", e.g. "Pune, IN"')
    where.add_argument("--lat", type=float, help="latitude, north positive")
    where.add_argument("--lon", type=float, help="longitude, east positive")
    where.add_argument("--elevation", type=float, default=0.0, help="metres (sunrise)")
    zone = c.add_mutually_exclusive_group()
    zone.add_argument("--tz", help="IANA time zone; default: looked up from the coordinates")
    zone.add_argument("--utc-offset", type=_offset,
                      help="documented clock standard, e.g. +05:30 or --utc-offset=-04:00 "
                           "(no DST applied)")
    c.add_argument("--precision", default="minute",
                   choices=["minute", "rounded_5", "rounded_15", "hour"],
                   help="how precise the recorded time is (sets the uncertainty)")
    c.add_argument("--uncertainty", type=_uncertainty,
                   help="± minutes, 0–720 (overrides --precision)")
    c.add_argument("--method", default=None,
                   help="parashari (default) or bnn; the method decides the default profile")
    c.add_argument("--profile", default=None,
                   help="calculation profile ID (default: the method's default profile)")
    c.add_argument("--native-gender", choices=["male", "female"],
                   help="optional BNN input: Jupiter or Venus signifies the native (INP-8)")
    c.add_argument("--vargas", default="D1,D9,D10",
                   help="divisional charts to draw, e.g. D1,D9 (any of D1…D60)")
    c.add_argument("--varga-table", default=None,
                   help='divisional signs to tabulate, comma-separated, or "all" '
                        "(default: the charts drawn)")
    c.add_argument("--style", choices=["south", "north"], default="south",
                   help="chart layout: south (fixed signs) or north (fixed houses)")
    c.add_argument("--as-of", type=_instant, help="instant for the current dasha (default now)")
    c.add_argument("--json", action="store_true", help="machine-readable output")

    pl = sub.add_parser("places", help="look up a place name")
    pl.add_argument("query")

    e = sub.add_parser("ephemeris", help="manage the Swiss Ephemeris files")
    e.add_argument("action", choices=["fetch", "path"])
    return p


def _resolve_place(args, err) -> tuple[Place | None, float, float] | int:
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            err("give both --lat and --lon")
            return EXIT_NEEDS_INPUT
        if not (-90 <= args.lat <= 90 and -180 <= args.lon <= 180):
            err("latitude must be within ±90 and longitude within ±180")
            return EXIT_NEEDS_INPUT
        return None, args.lat, args.lon
    if not args.place:
        err("give --place or --lat/--lon")
        return EXIT_NEEDS_INPUT
    try:
        found = default_gazetteer().lookup(args.place)
    except RuntimeError as e:
        err(str(e))
        return EXIT_NEEDS_INPUT
    if found.status == "found":
        p = found.place
        return p, p.latitude, p.longitude
    if found.status == "ambiguous":
        err(f'"{args.place}" matches several places; add the state and country, or give '
            "the coordinates:")
        for p in found.candidates:
            err(f'  --place "{p.name}, {p.state}, {p.country_code}"   or   '
                f"--lat {p.latitude:.4f} --lon {p.longitude:.4f}")
    else:
        err(f'no place named "{args.place}". Try the official name or --lat/--lon.')
        if found.suggestions:
            err("Did you mean: " + "; ".join(found.suggestions[:5]))
    return EXIT_NEEDS_INPUT


def _varga_list(text: str, known: tuple[str, ...]) -> tuple[str, ...]:
    if text.strip().lower() == "all":
        return known
    items = tuple(dict.fromkeys(v.strip().upper() for v in text.split(",") if v.strip()))
    unknown = [v for v in items if v not in known]
    if unknown:
        raise ValueError(f"unknown varga {', '.join(unknown)}; available: {', '.join(known)}")
    return items


def cmd_chart(args, out, err) -> int:
    from astro.calc.refdata import load_refdata
    from astro.cli.render import render
    from astro.cli.report import ChartRequest, build

    home = astro_home()
    if args.profile and not (home / "profiles" / "calc" / f"{args.profile}.yaml").is_file():
        known = sorted(p.stem for p in (home / "profiles" / "calc").glob("*.yaml"))
        err(f"unknown profile {args.profile!r}; available: {', '.join(known)}")
        return EXIT_NEEDS_INPUT
    methods = sorted(p.stem for p in (home / "profiles" / "method").glob("*.yaml"))
    method = args.method or "parashari"
    if method not in methods:
        err(f"unknown method {method!r}; available: {', '.join(methods)}")
        return EXIT_NEEDS_INPUT
    known_vargas = load_refdata(home / "ontology").varga_ids()
    try:
        vargas = _varga_list(args.vargas, known_vargas)
        table = vargas if args.varga_table is None else _varga_list(args.varga_table,
                                                                     known_vargas)
    except ValueError as e:
        err(str(e))
        return EXIT_NEEDS_INPUT
    resolved = _resolve_place(args, err)
    if isinstance(resolved, int):
        return resolved
    place, lat, lon = resolved
    y, m, d = args.date
    req = ChartRequest(
        year=y, month=m, day=d, local_time=args.time, latitude=lat, longitude=lon,
        place=place, timezone=args.tz, utc_offset_minutes=args.utc_offset,
        calendar=args.calendar, precision=args.precision, uncertainty_minutes=args.uncertainty,
        method=method, method_given=args.method is not None, profile_id=args.profile,
        native_gender=args.native_gender, vargas=vargas, varga_table=table,
        as_of=args.as_of, elevation_m=args.elevation, place_query=args.place,
        place_source=default_gazetteer().source if place is not None else None)
    try:
        report = build(req)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(str(x) for x in er['loc'])}: {er['msg']}"
                             for er in e.errors())
        err(f"invalid input: {problems}")
        return EXIT_NEEDS_INPUT
    except CalcError as e:
        err(f"{e.reason.value}: {e.detail}")
        if e.reason.value == "ephemeris_unavailable":
            err("run `astro ephemeris fetch` (or set ASTRO_EPHE to the ephemeris directory)")
            return EXIT_ERROR
        return EXIT_UNSUPPORTED
    n = report.normalization
    if not report.ok:
        err(f"{n.reason.value if n.reason else n.status}: {n.detail}")
        if n.candidates_utc:
            local = datetime(y, m, d, args.time.hour, args.time.minute, args.time.second)
            err("choose the clock reading with one of" +
                (" (in place of --tz):" if args.tz else ":"))
            for c in n.candidates_utc:
                minutes = (local - c.replace(tzinfo=None)).total_seconds() / 60
                # the = form: argparse would read a bare "-04:00" as an option
                err(f"  --utc-offset={format_offset(minutes)[3:]}   (= {c:%Y-%m-%d %H:%M} UTC)")
        return EXIT_NEEDS_INPUT if n.status == "needs_input" else EXIT_UNSUPPORTED
    pos = report.results.get("positions")
    if pos is None or pos.status.value != "ok":
        reason = pos.reason.value if pos is not None and pos.reason else "failed"
        if reason == "out_of_range":
            c = report.profile.ephemeris.coverage
            err(f"out_of_range: the installed ephemeris covers {utc_from_jd(c.start_jd):%Y-%m-%d}"
                f" until {utc_from_jd(c.end_jd):%Y-%m-%d} (profile {report.profile.id}); this "
                "birth is outside it")
            return EXIT_UNSUPPORTED
        err(f"{reason}: {pos.detail if pos is not None else ''}")
        return EXIT_ERROR
    if args.json:
        out(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        out(render(report, args.style))
        if place is not None:
            out(ATTRIBUTION)
    return EXIT_OK


def cmd_places(args, out, err) -> int:
    try:
        found = default_gazetteer().lookup(args.query, limit=20)
    except RuntimeError as e:
        err(str(e))
        return EXIT_ERROR
    if found.status == "not_found":
        err(f'no place named "{args.query}"')
        for s in found.suggestions:
            err(f"  did you mean: {s}")
        return EXIT_NEEDS_INPUT
    for p in found.candidates:
        out(f"{p.label:<60} {p.latitude:9.4f} {p.longitude:9.4f}  pop {p.population:,}")
    out(ATTRIBUTION)
    return EXIT_OK


def cmd_ephemeris(args, out, err) -> int:
    from astro.ephemeris_fetch import fetch

    home = astro_home()
    dest = ephemeris_dir(home)
    if args.action == "path":
        out(str(dest))
        return EXIT_OK
    profiles = sorted((home / "profiles" / "calc").glob("*.yaml"))
    return EXIT_OK if fetch(profiles, dest, log=out) else EXIT_ERROR


def main(argv: list[str] | None = None, out=None, err=None) -> int:
    out = out or (lambda s: print(s))
    err = err or (lambda s: print(s, file=sys.stderr))
    args = build_parser().parse_args(argv)
    try:
        return {"chart": cmd_chart, "places": cmd_places,
                "ephemeris": cmd_ephemeris}[args.command](args, out, err)
    except ResourceError as e:
        err(str(e))
        return EXIT_ERROR
    except CalcError as e:
        err(f"{e.reason.value}: {e.detail}")
        return EXIT_UNSUPPORTED if e.reason.value != "ephemeris_unavailable" else EXIT_ERROR


