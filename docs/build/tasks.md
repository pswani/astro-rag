# Calculation layer — build task list

| | |
|---|---|
| **Source** | [calc-review.md](../design/calc-review.md) §1 (what can be built now), §3 (modularity M1–M8) |
| **Scope** | Independent items only: no LLM, corpus, reviewed rule card or open reviewer decision is needed |
| **Loop per task** | plan → review → fix → code → tests → review → fix → test |

Status: `[ ]` todo · `[~]` in progress · `[x]` done (tests green) · `[!]` blocked (reason given)

Undecided conventions (calc-review §5, decisions 2–4) are implemented as **profile options**, with every variant supported where it is cheap. `parashari_v1` carries a provisional value and lists the field under `provisional:` until the reviewer confirms it.

## B0 Project skeleton

- [x] B0.1 `pyproject.toml` (src layout, Python ≥ 3.11, pinned runtime deps), `ruff`, `pytest` config
- [x] B0.2 `scripts/fetch_ephemeris.py`: download the Swiss Ephemeris files with SHA-256 pinning into `data/ephe/` (git-ignored)
- [x] B0.3 import-linter contract: `astro.calc` imports nothing from retrieval, workflows, store or llm (M7)
- [x] B0.4 GitHub Actions CI: lint, import contracts, tests (with ephemeris fetch)

## B1 Core primitives (`astro.calc.core`)

- [x] B1.1 `angles`: `norm360`, `signed_diff`, `unwrap`, `sign_index`, `deg_in_sign`, `nakshatra_index`, `pada`, DMS formatting
- [x] B1.2 `timescale`: civil date (Gregorian / proleptic Julian) ↔ JD(UT), UTC datetime ↔ JD, ΔT recorded
- [x] B1.3 `intervals`: half-open UTC `Interval`, overlap, containment, segmentation at boundary instants
- [x] B1.4 `canonical`: RFC 8785 canonical JSON, 1e-9 float rounding, SHA-256 content hash (CALC-9)
- [x] B1.5 `status`: reason codes (design §12.9) and the `Status` enum

## B2 Contracts

- [x] B2.1 `model`: typed `ChartFact` (discriminated values), `Relation`, `DashaPeriod`, `TransitEvent`, `FeatureResult` (M5, §3.3)
- [x] B2.2 `profile`: `CalcProfile` (Pydantic, closed enums, frozen), YAML loader, content hash, `unsupported_profile` (CALC-3, G-P1)
- [x] B2.3 `profiles/calc/parashari_v1.yaml` and `bnn_v1.yaml` with provisional fields listed
- [x] B2.4 Ontology core YAML: grahas (lords, exaltation/debilitation, moolatrikona, own signs, natural friendship, Vimshottari years), rashis, nakshatras, dasha_systems, vargas (D1/D9/D10 spec, G-V1); `status: provisional`
- [x] B2.5 `refdata`: `ReferenceData` protocol + YAML implementation + referential-integrity check (M6, KNW-11)

## B3 Engines

- [x] B3.1 Ephemeris port (`Ephemeris` protocol) (M1)
- [x] B3.2 `SwissEphemeris` adapter: positions, ayanamsa, Lagna and cusps, sunrise/sunset, Sun/Moon crossings; refuse Moshier fallback; record versions
- [x] B3.3 Capability check: profile `ephemeris.coverage` → `out_of_range` (G-C1)
- [x] B3.4 `solver`: bracket + Brent root finding, station finding, contact (minimum) detection, monotone-segment partition (§7.8)
- [x] B3.5 Feature engine: `Feature` protocol, registry, DAG resolution with `graphlib`, per-chart memo, `CachePort` + in-memory cache (M2, CALC-8)
- [x] B3.6 Strategy registries for ayanamsa, house system and varga construction (M3) — ayanamsa, house system and sunrise are closed maps in the Swiss adapter; varga construction is the data-driven spec (B5.5)

## B4 Normalization prerequisites (§5.1)

- [x] B4.1 Birth input model: date + calendar, local time, precision, uncertainty defaults (INP-3, design §6.3)
- [x] B4.2 Time-zone resolution: IANA zone or explicit offset; gap → `invalid_local_time`, fold → both candidates (INP-2, §6.2.3)
- [x] B4.3 Coordinates → IANA zone via `timezonefinder` when no zone is supplied
- [x] B4.4 Normalized input → chart ID via HMAC with an injected key (§5.3)
- [!] B4.5 GeoNames gazetteer import and place ranking — needs the GeoNames dump provisioned; deferred

## B5 Phase-1 features

- [x] B5.1 Positions: sidereal longitude, latitude, speed, retrograde for Sun…Saturn, Rahu, Ketu (derived) and Lagna; sign, degree, nakshatra, pada, nakshatra lord (CALC-1, CALC-2 subset; G-C3, G-C4 as options)
- [x] B5.2 Houses: whole-sign and Sripati placement; frames Lagna / Chandra / Surya / any graha (CALC-4)
- [x] B5.3 Lordships, occupants, parivartana, dispositor chains with terminal kind (REL-1 subset)
- [x] B5.4 Friendship: natural (ontology), temporal, compound panchadha (REL-2 subset)
- [x] B5.5 Varga engine (data-driven spec) + D1/D9/D10; vargottama (VAR-1)
- [x] B5.6 Panchanga: tithi + paksha, nakshatra, nitya yoga, karana with start/end; vara by sunrise; `no_sunrise` (PAN-1, PAN-2)
- [x] B5.7 Vimshottari: birth balance, MD/AD/PD tree (SD optional), `active_chain`, `periods_in`, sandhi flags (DAS-1, DAS-2, DAS-4)
- [x] B5.8 Condition: dignity, combustion, graha yuddha, gandanta, sandhi — built as provisional profile options (D3)
- [x] B5.9 Aspects and conjunctions — built as provisional profile options (D4)

## B6 Later-phase pure features

- [x] B6.1 Transit positions at the as-of date relative to the natal Lagna, Moon and planets (TRN-1)
- [x] B6.2 Event search: sign/nakshatra/pada ingresses, stations, conjunctions with natal points, returns; all loop crossings (TRN-2)
- [x] B6.3 Named states as intervals: Sade Sati with phase, Ashtama and Kantaka Shani, Jupiter from the Moon (TRN-3 subset)
- [x] B6.3b Jupiter–Saturn double transit and Rahu–Ketu axis over natal points (D5)
- [x] B6.4 Eclipses with natal contact within an orb (TRN-5)
- [x] B6.5 Birth-time sensitivity: Lagna sign/nakshatra, Moon nakshatra/pada, house placements (whole-sign), D9/D10 Lagna, dasha boundaries (CALC-7) — built into each feature; Sripati placements use a 2-min Lagna grid (margins ±1 step, G-C9)
- [x] B6.6 BNN relations: trines, 2nd, 12th, 7th from each graha, exchanges, conjunction by sign, retro-in-previous-sign variant; BNN karaka roles (SCH-BNN-1, SCH-BNN-2) — nodes excluded from the retro variant, recorded in provenance for the reviewer
- [x] B6.7 BNN transit triggers: Jupiter, Saturn and the nodes entering the sign of, or a trine to, a natal planet (TRN-6; added during the build)

## B7 Verification

- [x] B7.1 Property tests (Hypothesis): index ranges, dasha tiling, `active_chain` uniqueness, `periods_in` = brute force, varga closed forms, loop crossings (calc-review §4.3)
- [x] B7.2 Oracle tests against PyJHora (test-only, AGPL): positions, Lagna, panchanga, D9/D10, Vimshottari — 8 charts, 48 checks; AD starts agree to < 1 min under matched conventions
- [x] B7.3 Determinism: byte-identical re-run of a full feature run (CALC-9) — same bytes across re-runs, the cache and a fresh process
- [x] B7.4 Review pass over the whole layer; fix findings — 10 findings, all fixed with regression tests (`tests/calc/test_review_fixes.py`); see below

## C Standalone chart CLI (`astro chart`)

- [x] C1 Offline gazetteer adapter over the GeoNames-derived `reverse_geocode` city table (155k places): `City[, State][, Country]` parsing, accent-insensitive matching, ambiguity → candidate list (design §6.2.2; partial B4.5)
- [x] C2 Resource discovery: ontology/profiles via `ASTRO_HOME` or upward search; ephemeris via `ASTRO_EPHE` or `data/ephe`; `astro ephemeris fetch`
- [x] C3 Chart assembly: normalize → engine run (positions, houses, vargas, panchanga, Vimshottari, dasha_active) → one report object; JSON output
- [x] C4 Text rendering: South Indian and North Indian charts for D1/D9/D10, planet table with sensitivity flags, panchanga in local time, Vimshottari summary, provisional-setting and assumption notes
- [x] C5 CLI: `astro chart`, `astro places`, exit codes (0 ok, 2 needs input, 3 unsupported), `python -m astro`
- [x] C6 Tests: gazetteer, renderers, CLI end-to-end (incl. ambiguous place, DST fold, unknown time), review and fix

## D Alignment with requirements and design (review → fix → test loop)

Gaps found by tracing requirements §5.1–§5.8 and design §6–§7 against the code. Undecided conventions
are implemented as profile options with provisional values, listed in `provisional:`.

- [x] D1 INP-1: record place provenance (source, query, label, location ID when available) in the normalization
- [x] D2 CALC-3: Placidus house system; `unsupported_feature` where cusps are undefined (polar latitudes)
- [x] D3 CALC-2: condition — dignity (with precedence and friendship basis), combustion, graha yuddha, gandanta, rashi sandhi, each with sensitivity (G-C5…G-C8)
- [x] D4 REL-1: Parashari graha drishti with special aspects, node aspects per profile, conjunctions (same sign or orb), aspects received (G-R1)
- [x] D5 TRN-3: Jupiter–Saturn double transit and Rahu–Ketu axis over natal points as intervals
- [x] D6 DAS-5: period-lord context for the active MD/AD/PD lords, holding fact IDs (G-D3)
- [x] D7 Design §7.10 / INP-5: `MethodAdapter` protocol, method profiles, registry; default method stated in output
- [x] D8 VAR-2: remaining Shodashvarga with one declared Parashari construction each (spec extended for steps, absolute starts, elements and tables); PyJHora oracle
- [x] D9 CLI: dignity and condition flags, aspects, any varga, method and provisional notes
- [x] D10 User guide (README): install, inputs, every report section, options, profiles, JSON, exit codes, accuracy, FAQ, privacy, glossary; every example command checked
- [x] D11 Review loop until clean: code review, alignment re-check, fixes with regression tests — 7 rounds; round 7 found no correctness defects; traceability in [alignment.md](alignment.md)

Still out of scope: functional roles (G-R2 needs a sourced table), Shadbala (G-S2), PAN-3 (G-PN2), phase-7 items.

### D11 review rounds

| Round | Main findings | Root-cause fix |
|---|---|---|
| 1 | Polar Placidus occupants empty-and-stable; multi-war outcome overwrite; orb-conjunction sensitivity; built-ins only via entry points; draft gate defeated; `--vargas` meaning changed | Unknown occupants; loser-if-any; orb crossings; built-in registration; purpose-based gate; `--varga-table` |
| 2 | Aspect/conjunction sensitivity too lax or too strict; lordship sensitivity; incomplete orbs crash; plugin override; frame naming under cusp systems; country aliases | Reachable-sign rule; validated orbs; isolated plugins; `lagna_rashi`; aliases |
| 3 | The reachable-sign rule assumed ±1 sign (fast Lagna); war winners and the combustion orb could flip unnoticed | **Exact piecewise sensitivity**: facts evaluated between solved change instants; ground-truth sampling test |
| 4 | Duplicate solves; approximate cusp houses; war relations scoped too widely; cache growth | One per-chart store of change instants; exact cusp crossings; per-pair scope; versioned caches |
| 5 | Interval ends decided by crossing direction and root rounding | Value-based ends; no search shift; shared stations; canonical angle keys |
| 6 | Change next to t; proxies disagreeing with the facts' rules at edges | t as an edge; real rules everywhere |
| 7 | No correctness defects; cleanups | Applied |

### C6 review findings

| # | Finding | Fix |
|---|---|---|
| 1 | A 29 February birth crashed the dasha table (`replace(year=+120)`) | 120 years as a span in days |
| 2 | "Los Angeles, CA", "Atlanta, Georgia", "Springfield, IL" read as countries | A qualifier narrows by country *or* state; an exact state beats a prefix |
| 3 | Unknown-time North D9/D10 rotated on the D1 Moon | Chandra lagna uses the Moon's sign in that varga |
| 4 | Missing ephemeris files exited 3 with no hint | Exit 1 with "run `astro ephemeris fetch`" |
| 5 | Month 13, unknown `--profile`, out-of-range offsets and uncertainty raised tracebacks; `+05:75` was accepted | Validated: exit 2 with a message |
| 6 | `astro places` crashed without `reverse_geocode` | Clean message, exit 1 |
| 7 | Crowded signs silently dropped bodies | South cells grow; North triangles show "+n more" |
| 8 | The ambiguity hint could loop | Exact-state match; every candidate also shows `--lat/--lon` |
| 9 | `ephemeris fetch` tracebacked offline and could leave a truncated file | Errors logged per file; temp file + atomic rename |
| 10 | The DST-fold hint conflicted with `--tz` | Hint says "in place of --tz" |
| — | Lazy imports defeated; one-sided dasha shift line | `cli.fmt` helper; both directions shown |

## B7.4 review findings

| # | Finding | Fix |
|---|---|---|
| 1 | Nakshatra and pada ingresses at the same instant got the same event ID | ID carries the ingress kind and pada |
| 2 | One dependency cycle failed every requested feature | Only cycle members fail; dependents become `dependency_unavailable` |
| 3 | Exceptions in `requires()` or the cache key escaped `Engine.run()` | Both become feature-local `failed` / `tool_error` |
| 4 | A tz-aware `local_time` was misread as a DST gap, or its offset dropped | Rejected at input: the clock time must be naive |
| 5 | Transit retrograde ignored the profile's node rule | Shared `is_retrograde()` |
| 6 | `dasha_active` reported a naive `as_of` as `tool_error` | Shared `parse_utc_instant()` → `missing_input` |
| 7 | `dasha_active` hard-coded depth 3; absent levels reported sandhi `False` | Uses the profile levels; absent levels are `unknown` |
| 8 | `set_ephe_path` on every call (6× slower) | Set once; the file actually read is verified after every calculation, so a path changed elsewhere is detected and reset |
| 9 | Three sensitivity searches per body; vargottama repeated D9 | One pada-width search classifies sign/nakshatra/pada; vargas reuse it |
| 10 | Stations and samples recomputed per crossing call | `crossings(stations=…)`; raw samples reused |

A full 15-feature run went from about 1.6 s to 0.27 s after 8–10.

## How to run

```
pip install -e ".[dev,oracle]"
python scripts/fetch_ephemeris.py      # Swiss Ephemeris files, SHA-256 pinned in the profiles
ruff check src tests scripts && lint-imports && pytest
```

## Change log

| Date | Change |
|---|---|
| 2026-10-19 | List created |
| 2026-10-19 | D done: requirement gaps closed (CALC-2, CALC-3 Placidus, REL-1, TRN-3, DAS-5 partial, VAR-2, §7.10 adapters, INP-1 provenance); 7 review rounds; 412 tests; [alignment.md](alignment.md) |
| 2026-10-19 | C done: `astro chart` / `astro places` / `astro ephemeris`, 28 CLI tests, 10 review findings fixed. The offline city table covers B4.5 for names in GeoNames cities1000; alternate names (e.g. Bangalore) still need the full dump |
| 2026-10-19 | B7 done: 168 tests, clean-venv CI check, oracle extra declares PyJHora's undeclared imports (CI fails instead of skipping) |
| 2026-10-19 | B6 done (B6.3b blocked on G-R1). Real-data fixture: Saturn crosses natal Mercury three times in 2026–27 (TRN-2 acceptance); Sade Sati phases verified on a synthetic ephemeris |
| 2026-10-19 | B4, B5.1–B5.7, B7.2 done. Oracle findings: PyJHora defaults to true geometric positions (Sun ~20″ from apparent), the true node and a per-chart *true* sidereal year; `drik.dhasavarga` uses cyclic (parivritti) D10, so `charts.divisional_chart(chart_method=1)` is the Parashari oracle. Recorded as G-C12 and G-D4 in calc-review |
| 2026-10-19 | B0–B3 done. Findings fixed during the loop: exact boundary indexing (Hypothesis found 30° → wrong pada via `floor(λ / (10/3))`); contact detection uses adjacent monotone pieces instead of a 1-day window; Swiss Ephemeris coverage start corrected to JD 2378497.0 (2378496.5 already falls back to Moshier); nutation does not change sidereal positions (G-C4 downgraded) |
