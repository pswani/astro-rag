# Calculation layer — build design notes

| | |
|---|---|
| **Date** | 2026-10-19 |
| **Implements** | [calc-review.md](../design/calc-review.md) §3 (M1–M8) for the tasks in [tasks.md](tasks.md) |
| **Normative** | [design.md](../design/design.md) §6, §7. Where these notes add detail, design.md still wins on conflict. |

## 1. Layering

```
astro.calc.core        pure maths and envelopes; no third-party astronomy imports
astro.calc.model       Pydantic result models
astro.calc.profile     CalcProfile + loader
astro.calc.refdata     ReferenceData protocol + YAML implementation (reads ontology/)
astro.calc.ephemeris   Ephemeris protocol + SwissEphemeris adapter (the only module importing swisseph)
astro.calc.solver      crossings, stations, contacts (scipy.brentq); pure functions of callables
astro.calc.sensitivity birth-time sensitivity on top of the solver
astro.calc.engine      Feature protocol, registry, DAG, cache port
astro.calc.features    positions, houses, relations, friendship, vargas, panchanga
astro.calc.dasha       DashaSystem protocol, Vimshottari
astro.calc.transits    transit positions, events, named states, eclipses
astro.methods.bnn      BNN relations and karaka roles
astro.normalize        birth input → normalized instant, chart ID
```

`import-linter` enforces two rules: `astro.calc` never imports `astro.normalize` or `astro.methods`, and only `astro.calc.ephemeris.swiss` imports `swisseph`.

## 2. Time and angles

- Computation uses **JD (UT)** floats. Models expose timezone-aware **UTC `datetime`s**, rounded to the microsecond.
- `core.timescale` implements Meeus' JD algorithm for Gregorian and proleptic-Julian civil dates, so it doesn't depend on Swiss Ephemeris. Tests check it against `swe.julday`.
- Longitudes are degrees in `[0, 360)`. `signed_diff(a, b)` ∈ `(−180, 180]`.
- Index helpers return **0-based** indices. Ontology IDs carry the names.

## 3. Ephemeris adapter (M1)

- Swiss Ephemeris keeps global state (ephemeris path, sidereal mode). The adapter sets the sidereal mode on every call, under a process-wide lock.
- **No silent Moshier fallback** (probe: a 1500 CE date with only `*_18` files returned `FLG_MOSEPH`). Every result's return flag is checked for `FLG_SWIEPH`. A fallback raises `EphemerisError(out_of_range)`. The adapter also refuses to start if a profile-listed file is missing or its SHA-256 differs.
- **Coverage** is declared in the profile (`ephemeris.coverage`) and checked before any call. The `*_18` files cover JD 2378496.5 to 2597641.5 (1800-01-01 to 2399-12-31). Tests confirm this.
- **Nutation (G-C4):** the probe shows sidereal longitudes from `FLG_SIDEREAL` are identical with and without `FLG_NONUT`. Swiss Ephemeris subtracts a matching ayanamsa, so the choice only affects the *reported* ayanamsa value. The adapter reports both. G-C4 is downgraded to Minor.
- **Ketu** = Rahu + 180°, latitude negated, same speed. It is never a separate ephemeris call.
- **Sunrise:** `rise_trans` with `BIT_HINDU_RISING` (disc centre, no refraction) or plain `CALC_RISE` (upper limb with refraction), per profile. Elevation comes from the input (default 0, recorded). A circumpolar result returns `None`.

## 4. Solver

One function serves ingresses, panchanga boundaries, conjunctions and sensitivity:

```
crossings(lon, t0, t1, *, step, speed=None, width=None, offset=0, targets=(), contact_tol=None)
```

1. If `speed` is given, find stations in `[t0, t1]`: bracket sign changes of speed on the grid, then refine with Brent.
2. Sample points = grid (spacing `step`) ∪ stations ∪ {t0, t1}. Between consecutive sample points the motion is **monotone**, and `step` keeps the movement under 180° so unwrapping is unambiguous.
3. For each consecutive pair, list every boundary (`offset + k·width`, or a target + `k·360`) strictly between the two unwrapped values. Each boundary is crossed exactly once there, so `brentq` on `lon_unwrapped(t) − boundary` gives the instant to 1 s.
4. If `contact_tol` is set, check every station for a grazing contact: `|signed_diff(lon(station), target)| ≤ tol` with no crossing in the adjacent pieces.

This gives all three crossings of a retrograde loop (TRN-2) and catches a cross-and-recross near a station (CALC-7 acceptance).

## 5. Sensitivity (CALC-7)

For a fact derived from a longitude with boundary width `w` (sign 30°, nakshatra 40/3°, pada 10/3°, varga part 30/N°):

```
assess(lon, speed, t, u, w) → (sensitivity, margin_before_min, margin_after_min)
```

- Run `crossings` over `[t − u, t + u]`. Any crossing means `sensitive`, otherwise `stable`.
- The margins are the distances in minutes from `t` to the nearest crossing on each side within the interval (`None` if none).
- A whole-sign house placement combines the planet's sign assessment with the Lagna's: sensitive if either is, nearest margin wins.
- With an **unknown time**, `t` = local noon and `u` = 720 min (design §6.3). Lagna-dependent facts become `unknown` with `value = None` and are not assessed.
- Step per body: Lagna 2 min, Moon 1 h, Sun/Mercury/Venus/Mars 12 h, Jupiter/Saturn/nodes 2 days, true node 6 h (G-T1). The step is capped at `u` so short intervals are still sampled at their ends.

## 6. Models (M5, calc-review §3.3)

- `ChartFact.value` is `bool | int | float | str | tuple[str, ...] | None`. A `FACT_KINDS` table maps each `kind` to its value type, and a validator enforces it. `None` is allowed only with `sensitivity = "unknown"`.
- Fact IDs follow design §5.3: `<chart>/<kind>/<subject>[/<frame>][/<varga>]`.
- `FeatureResult.status` ∈ `ok | unknown | unsupported | failed`, with `reason` from the design §12.9 codes plus `no_sunrise`, `dependency_unavailable` and `ephemeris_unavailable`.

## 7. Feature engine (M2)

- `FeatureRequest(feature_id, params)` with `params` as a sorted tuple, so requests are hashable and canonical.
- `Feature.requires(params) -> list[FeatureRequest]` and `Feature.compute(ctx, deps, params) -> FeatureResult`.
- `Engine.run(ctx, requests)` expands requirements transitively, orders them with `graphlib.TopologicalSorter` (a cycle raises `dependency_cycle`), memoizes per run and consults a `CachePort`.
- Cache key = SHA-256 of canonical `(chart_id, feature_id, params, engine_version, profile_hash, ephemeris_files_sha)`.
- A dependency with status ≠ `ok` makes its dependent return `unknown` with `dependency_unavailable`. Exceptions become `failed` / `tool_error`. A `FeatureError(reason)` becomes `unsupported` with that reason.
- `ChartContext` = `(chart_id, NormalizedBirth, CalcProfile, Ephemeris, ReferenceData)`. There are no wall-clock reads; `as_of` is a parameter.

## 8. Profiles (G-P1)

- `CalcProfile` is frozen and uses `extra="forbid"`, so an unknown key or enum value raises `ProfileError(unsupported_profile)`.
- Fields not yet decided by the reviewer carry a provisional value and appear in `provisional: [dotted.path, …]`. A validator checks each path exists.
- `content_hash` = SHA-256 of canonical JSON.

## 9. Ontology core and the varga spec (G-V1)

- Files: `ontology/grahas.yaml`, `rashis.yaml`, `nakshatras.yaml`, `panchanga.yaml` (tithis, karanas, nitya yogas, varas), `dasha_systems.yaml`, `vargas.yaml`, `karaka_schemes.yaml`. Every file carries `status: provisional` until the reviewer signs off.
- Only undisputed data needed by the tasks is included: sign lords, natural friendship of the seven grahas, nakshatra lords, Vimshottari years, names. Exaltation, moolatrikona, combustion and node co-lordship wait for decision 3.

The varga spec:

```yaml
D9: {divisions: 9,  parts: equal, start: {rule: by_modality, movable: 0, fixed: 8, dual: 4}, source: …}
D10: {divisions: 10, parts: equal, start: {rule: by_parity, odd: 0, even: 8}, source: …}
```

`varga_sign = (sign + offset(sign) + floor(deg_in_sign / (30 / N))) mod 12`. The offset depends on the rule (`same` = 0).

## 10. Vimshottari

- Moon nakshatra `n`, fraction traversed `f`, lord `L = seq[n mod 9]`. The first MD starts at `t_birth − f · years(L) · year_days`.
- MDs are generated cyclically until `end ≥ t_birth + span_years · year_days` (default 120).
- Children start with the parent's lord and follow the cyclic order. Duration = `parent · years(child) / 120`.
- `boundary_margin_days` = boundary shift when birth is moved by `−u` and `+u`. All boundaries shift together while the nakshatra is unchanged. A nakshatra change inside the interval is reported as a sequence change.
- Sandhi: `as_of` within `profile.dasha.sandhi_margin_days[level]` of an MD or AD boundary.

## 11. Review of these notes (step 2 of the loop)

| Check | Result |
|---|---|
| CALC-3: unknown setting → explicit status | `extra="forbid"` + closed enums → `unsupported_profile` |
| CALC-9: determinism | No wall clock; canonical JSON; profile hash and file SHAs in the key |
| No silent fallback (design §7.1) | Return-flag check, coverage check, file SHA check |
| Wrap-around false brackets | Unwrapping on a grid with movement < 180° per step; never bracket on a raw wrapped difference |
| Lagna non-monotone at high latitude | 2-min grid without a station assumption; finer than any sign/nakshatra/pada change of a monotone Lagna |
| Global Swiss Ephemeris state | Sidereal mode set per call under a lock |
| Unknown birth time (INP-3) | Lagna facts `unknown`; Moon facts assessed over the whole day |
| Disputed values never chosen silently | Not included, or listed under `provisional` |
| **Fix applied:** first draft put sensitivity in a separate later feature, so facts would ship without it | Sensitivity is assessed inside each feature that emits a longitude-derived discrete fact |
| **Fix applied:** first draft let `ChartFact.value` be `Any` | Kind → type table with a validator |
