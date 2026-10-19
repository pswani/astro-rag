# astro-rag

Jyotish agentic RAG: requirements and design in [`docs/`](docs/), and the deterministic
calculation layer in `src/astro/` ([build task list](docs/build/tasks.md)).

## `astro` — natal charts from the shell

```sh
pip install -e ".[geo]"          # geo: offline place names and time-zone lookup
astro ephemeris fetch            # Swiss Ephemeris files (SHA-256 pinned)

astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN"
astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN" --style north
astro chart --date 1990-07-15 --time 04:10 --lat -33.87 --lon 151.21     # zone from coordinates
astro chart --date 1890-06-01 --time 06:42 --place Pune --utc-offset +05:53  # documented standard
astro chart --date 1985-03-14 --place Pune                                # time unknown
astro chart ... --json                                                    # machine-readable
astro places Springfield
```

Output: Rasi, Navamsa and Dasamsa charts (South or North Indian), a planet table with
nakshatra, pada, house and varga signs, the panchanga at birth, and the Vimshottari periods with
the current dasha (`--as-of` to choose the instant).

- `*` marks a fact that changes within the birth-time uncertainty (`--precision`,
  `--uncertainty`); `?` marks a fact that cannot be known (e.g. the Lagna without a birth time,
  when the North chart falls back to Chandra lagna).
- An ambiguous place, a DST fold or gap, or an unknown calendar is never guessed: the command
  exits 2 and says what to add. Dates outside the installed ephemeris exit 3.
- Settings marked provisional in the profile await expert review and are listed in every report.
- Place data: [GeoNames](https://www.geonames.org/) (CC BY 4.0) via `reverse_geocode`.

Exit codes: 0 ok · 1 setup error · 2 more input needed · 3 unsupported.

## Development

```sh
pip install -e ".[dev,oracle]"
python scripts/fetch_ephemeris.py
ruff check src tests scripts && lint-imports && pytest
```
