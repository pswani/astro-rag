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

- [ ] B4.1 Birth input model: date + calendar, local time, precision, uncertainty defaults (INP-3, design §6.3)
- [ ] B4.2 Time-zone resolution: IANA zone or explicit offset; gap → `invalid_local_time`, fold → both candidates (INP-2, §6.2.3)
- [ ] B4.3 Coordinates → IANA zone via `timezonefinder` when no zone is supplied
- [ ] B4.4 Normalized input → chart ID via HMAC with an injected key (§5.3)
- [!] B4.5 GeoNames gazetteer import and place ranking — needs the GeoNames dump provisioned; deferred

## B5 Phase-1 features

- [ ] B5.1 Positions: sidereal longitude, latitude, speed, retrograde for Sun…Saturn, Rahu, Ketu (derived) and Lagna; sign, degree, nakshatra, pada, nakshatra lord (CALC-1, CALC-2 subset; G-C3, G-C4 as options)
- [ ] B5.2 Houses: whole-sign and Sripati placement; frames Lagna / Chandra / Surya / any graha (CALC-4)
- [ ] B5.3 Lordships, occupants, parivartana, dispositor chains with terminal kind (REL-1 subset)
- [ ] B5.4 Friendship: natural (ontology), temporal, compound panchadha (REL-2 subset)
- [ ] B5.5 Varga engine (data-driven spec) + D1/D9/D10; vargottama (VAR-1)
- [ ] B5.6 Panchanga: tithi + paksha, nakshatra, nitya yoga, karana with start/end; vara by sunrise; `no_sunrise` (PAN-1, PAN-2)
- [ ] B5.7 Vimshottari: birth balance, MD/AD/PD tree (SD optional), `active_chain`, `periods_in`, sandhi flags (DAS-1, DAS-2, DAS-4)
- [!] B5.8 Condition: dignity, combustion, graha yuddha, gandanta, sandhi — waits for decision 3 (G-C5…G-C7)
- [!] B5.9 Aspects and conjunctions — waits for decision 4 (G-R1)

## B6 Later-phase pure features

- [ ] B6.1 Transit positions at the as-of date relative to the natal Lagna, Moon and planets (TRN-1)
- [ ] B6.2 Event search: sign/nakshatra/pada ingresses, stations, conjunctions with natal points, returns; all loop crossings (TRN-2)
- [ ] B6.3 Named states as intervals: Sade Sati with phase, Ashtama and Kantaka Shani, Jupiter from the Moon (TRN-3 subset; double transit waits for G-R1)
- [ ] B6.4 Eclipses with natal contact within an orb (TRN-5)
- [ ] B6.5 Birth-time sensitivity: Lagna sign/nakshatra, Moon nakshatra/pada, house placements (whole-sign), D9/D10 Lagna, dasha boundaries (CALC-7)
- [ ] B6.6 BNN relations: trines, 2nd, 12th, 7th from each graha, exchanges, conjunction by sign, retro-in-previous-sign variant; BNN karaka roles (SCH-BNN-1, SCH-BNN-2)

## B7 Verification

- [ ] B7.1 Property tests (Hypothesis): index ranges, dasha tiling, `active_chain` uniqueness, `periods_in` = brute force, varga closed forms, loop crossings (calc-review §4.3)
- [ ] B7.2 Oracle tests against PyJHora (test-only, AGPL): positions, Lagna, panchanga, D9/D10, Vimshottari
- [ ] B7.3 Determinism: byte-identical re-run of a full feature run (CALC-9)
- [ ] B7.4 Review pass over the whole layer; fix findings

## Change log

| Date | Change |
|---|---|
| 2026-10-19 | List created |
| 2026-10-19 | B0–B3 done. Findings fixed during the loop: exact boundary indexing (Hypothesis found 30° → wrong pada via `floor(λ / (10/3))`); contact detection uses adjacent monotone pieces instead of a 1-day window; Swiss Ephemeris coverage start corrected to JD 2378497.0 (2378496.5 already falls back to Moshier); nutation does not change sidereal positions (G-C4 downgraded) |
