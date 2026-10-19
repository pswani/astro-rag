# Calculation layer: build readiness, design gaps and reuse

| | |
|---|---|
| **Date** | 2026-10-19 |
| **Scope** | Requirements §5.2–§5.8 (CALC, PAN, VAR, REL/STR, DAS, TRN, SCH) and their design in [design.md](design.md) §7, §8, §10.2 |
| **Inputs** | [requirements.md](../req/requirements.md) rev 3, [design.md](design.md) rev 5 |
| **Status** | Review. The gaps marked **Blocking** need a decision in design.md before the named module is coded. |

These requirements are deterministic code (`AGT-1`, `CALC-9`, `OUT-2`). The chart workflow calls them, not the LLM (design §13.4). This review answers three questions:

1. What can be built now?
2. Is the design complete and modular enough to build from?
3. Which free, standard libraries and algorithms should be reused?

---

## 1. What can be built now

Nothing is implemented yet. "Now" means a component doesn't depend on the corpus, an LLM, reviewed rule cards or an open variant decision. Components scheduled for later phases are included when they are pure functions with no such dependency. Building them early de-risks phases 3–5.

### 1.1 Build order

Each layer depends only on the layers above it.

| Layer | Component | Module | Reqs | Design ph | Can start | Needs first |
|---|---|---|---|---|---|---|
| **L0 Primitives** | Angles (normalize, signed difference, unwrap), sign/nakshatra/pada indexing | `calc/core/angles.py` | CALC-2 | 1 | Now | — |
| | Time scales: civil → UTC → JD(UT/TT), Julian/Gregorian switch, ΔT recorded | `calc/core/timescale.py` | CALC-1, INP-1 | 1 | Now | — |
| | Half-open UTC intervals, overlap, segmentation | `calc/core/intervals.py` | DAS-2, APP-4 | 1 | Now | — |
| | Canonical serialization + hashing, status/reason-code envelope | `calc/core/canonical.py`, `status.py` | CALC-9, CALC-3 | 1 | Now | — |
| **L1 Contracts** | Calculation profile schema, loader, closed-enum validation, `unsupported_profile` | `calc/profile.py` | CALC-3 | 1 | Now | Profile fields in §2.2 (G-P1) |
| | Result models: `ChartFact`, `Relation`, `DashaPeriod`, `TransitEvent`, `FeatureResult` | `calc/model.py` | CALC-2, REL-3, DAS-1, TRN-2 | 1 | Now | §3.3 |
| | Ontology core loader + integrity CI (grahas, rashis, nakshatras, dasha_systems, vargas, karaka_schemes) | `ontology.py` | KNW-11 | 1 | Now (values `provisional` until reviewed) | Reviewer sign-off before phase-1 exit |
| **L2 Engines** | Ephemeris port + Swiss Ephemeris adapter + capability check per date/feature | `calc/ephemeris/` | CALC-1, INP-1 | 1 | Now | G-C1 |
| | Root-finding solver: bracketing, Brent, stations, contacts | `calc/solver.py` | PAN-1, TRN-2, CALC-7 | 1/4 | Now | — |
| | Feature registry + dependency resolution + cache port (in-memory first) | `calc/engine.py` | CALC-8 | 1 | Now | §3.2 |
| **L3 Phase-1 features** | Positions: longitude, latitude, speed, retrograde, Lagna, Rahu/Ketu | `features/positions.py` | CALC-1 | 1 | Now | G-C3, G-C4 |
| | Condition: dignity, combustion, graha yuddha, gandanta, sandhi, vargottama | `features/condition.py` | CALC-2 | 1 | **After decisions** | G-C5…G-C8 |
| | Houses per profile (whole-sign, Sripati) and alternative frames | `features/houses.py` | CALC-4 | 1/3 | Now | — |
| | Lordships, occupants, conjunctions, parivartana, dispositor chains, graha drishti | `features/relations.py` | REL-1 | 1 | **After decisions** | G-R1 |
| | Natural/temporal/compound friendship | `features/relations.py` | REL-2 | 3 | Now | — |
| | Generic varga engine + D1/D9/D10 | `features/vargas.py` | VAR-1 | 1 | Now | G-V1 (spec format) |
| | Panchanga five limbs with start/end, sunrise/sunset, vara | `features/panchanga.py` | PAN-1, PAN-2 | 1 | Now | — |
| | Vimshottari tree, `active_chain`, `periods_in`, sandhi flags | `dasha/vimshottari.py` | DAS-1, DAS-2, DAS-4 | 1/4 | Now | Sandhi margin (G-D2) |
| **L4 Pure, later phase, unblocked** | Transit positions, event search, named states, eclipses | `transits/` | TRN-1, TRN-2, TRN-3, TRN-5 | 4 | After the solver | G-T1, G-T3 |
| | Birth-time sensitivity | `features/sensitivity.py` | CALC-7, DAS-4 | 3 | After the solver | G-C9, G-C10 |
| | BNN relations and karaka roles | `methods/bnn/` | SCH-BNN-1, SCH-BNN-2 | 5 | Now (pure geometry and data) | `bnn.linked` semantics for rules only |
| | Remaining Shodashvarga | `features/vargas.py` | VAR-2 | 4 | After the varga engine | Tables transcribed with source |
| | Ashtakavarga BAV/SAV | `features/ashtakavarga.py` | STR-1 | 4 | Now | Bindu tables transcribed; G-S1 |
| **Prerequisite (§5.1)** | Normalizer: coordinates path, GeoNames import, tz from coordinates, fold/gap, precision defaults | `normalize/` | INP-1…INP-3 | 1 | Now | — |
| **Verification** | Calc eval harness: property tests, PyJHora oracle diff, byte-identical re-run | `evals/calc/` | EVAL-1, NFR-1 | 1 | Now | JHora exports from the reviewer for the exit gate |

### 1.2 Not yet: spec or input missing

| Component | Reqs | Why it waits |
|---|---|---|
| Shadbala, Bhava Bala | STR-2 | The design covers it in one sentence. It needs a component-by-component spec (G-S2). |
| Lunar month, samvatsara, ayana, ritu | PAN-3 | Variant conventions are undecided (G-PN2). |
| Period-lord context | DAS-5 | Needs functional roles (G-R2) and strength. A skeleton over available facts can be built earlier. |
| Gochara vedha, kakshya scoring | TRN-4 | Needs STR-1 and the vedha/kakshya tables (G-T4). |
| Persistent fact cache | CALC-8 | Needs the encrypted store (§16). Build against the cache port with an in-memory implementation now. **Update 2026-10-19:** designed in [phase1-foundations.md](phase1-foundations.md) §2.5 (`StoreFactCache`, Pydantic JSON, chart-scoped rows); the port gains `chart_id`. |
| Other dasha systems, muhurta kalas, upagrahas, varga variants, phase-7 adapters | DAS-3, PAN-4, CALC-5, VAR-4, SCH-JAI/KP/TAJ/PRS/MUH/CMP-1 | Phase 7. The design gives one line each. Each needs its own spec before its bundle starts. |
| C items | VAR-3, STR-3, TRN-7, SCH-LK-1, SCH-WES-1 | Not planned. |

---

## 2. Is the design complete?

**Verdict:** the design is strong on time handling, panchanga formulas, Vimshottari, the event solver and determinism. It is under-specified on:

- the convention choices that decide discrete facts (dignity, aspects, gandanta, sandhi, yuddha);
- Shadbala;
- the module interfaces (no feature registry, no ephemeris port, no result envelope, untyped fact values).

The first two are mostly decisions for the reviewer, recorded as profile fields. The third is a design addition (§3).

### 2.1 Gaps by area

**Positions and condition (CALC-1, CALC-2)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-C1 | The profile pins `sepl_18`/`semo_18`, which cover 1800–2400. Requirements rev 3 removed the year range, and the INP-1 acceptance requires pre-1900 and post-2100 fixtures. | **Blocking** for INP-1 acceptance | Install the full Swiss Ephemeris file set for the range wanted. Add `ephemeris.coverage: {start_jd, end_jd}` to the profile. The capability check reads it and returns `out_of_range`. Never fall back to Moshier (already decided). |
| G-C2 | ΔT uncertainty grows from seconds to hours for ancient and far-future dates. That moves the Lagna exactly like birth-time uncertainty, but §7.9 ignores it. | Minor | Add a ΔT uncertainty estimate (published σ(ΔT) model) to the CALC-7 interval. Record it in provenance. |
| G-C3 | Rahu/Ketu semantics are undefined: Ketu = Rahu + 180°; the mean node is always retrograde; the true node is sometimes direct. Retrograde affects rules and the BNN variant. | **Blocking** for positions | Profile field `nodes.retrograde: always \| by_speed`. Ketu is derived, never computed separately. |
| G-C4 | Ayanamsa "true" (with nutation) vs "mean" is not declared. | Minor (downgraded after a probe) | Swiss Ephemeris subtracts a matching ayanamsa, so sidereal longitudes are identical with or without `FLG_NONUT`. Only the *reported* ayanamsa value differs. Profile field `ayanamsa.nutation` controls the reported value. |
| G-C5 | Dignity is ambiguous in three ways: (a) precedence where exaltation, moolatrikona and own sign overlap (Moon in Taurus, Mercury in Virgo); (b) whether friend/enemy dignity uses natural or compound friendship; (c) dignity in vargas. | **Blocking** for CALC-2 | Profile field `dignity: {precedence: [exalted, moolatrikona, own, …], friendship_basis: natural \| compound}`. Degree ranges stay in the ontology with sources. |
| G-C6 | Graha yuddha: the orb is given, but not the winner rule (latitude, longitude or brightness, which differ by source). | **Blocking** for CALC-2 | Profile field `graha_yuddha.winner: north_latitude \| …`. |
| G-C7 | Gandanta and sandhi have no thresholds. Gandanta can mean the last pada, the last 3°20′ or a fixed arc. Rashi sandhi can be ±1°, ±0°48′ and so on. | **Blocking** for CALC-2 | Profile fields `gandanta.arc_deg` and `sandhi.arc_deg`, with source. |
| G-C8 | Combustion: the angle measured (longitude difference or true angular distance) is not stated. | Minor | Profile field `combustion.measure: longitude`. |
| G-C12 | *Found while building:* apparent (light-time + aberration) vs true geometric positions is not declared. The Sun differs by about 20.5″, beyond the 10″ tolerance. PyJHora uses true positions (`FLG_TRUEPOS`). | **Blocking** for NFR-1 fixtures | Profile field `position.apparent` (both supported, provisional). Must match the Jagannatha Hora export settings. |
| G-C13 | *Found while building:* mean vs true node changes Rahu/Ketu by up to about 1.5°. Already a profile field, but PyJHora defaults to the true node while `parashari_v1` uses the mean node. | **Blocking** for NFR-1 fixtures | Reviewer confirms `nodes.model` against the reference exports. |

**Profiles (CALC-3)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-P1 | The YAML example is illustrative, not a schema. Many conventions the features need have no field (G-C3…G-C8, G-R1, G-D2, G-T3). | **Blocking** | A Pydantic `CalcProfile` with closed enums, exported to JSON Schema and validated in CI. Add every field this review names. Profile content hash goes into provenance. |

**Sensitivity (CALC-7)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-C9 | "Placements derived from the Lagna inherit the Lagna's boundary times" holds only for whole-sign houses. Under Sripati or Placidus, a house placement changes when a cusp crosses a planet. | Minor (Sripati is a profile option) | Solve each placement on the cusp longitude. Varga Lagnas use the varga spec's boundary function (G-V1). |
| G-C10 | When the Moon crosses a nakshatra boundary, the whole Vimshottari sequence changes, not just a shift. | Minor | Record a sequence change as its own sensitivity reason. Within one nakshatra, boundaries shift linearly with the Moon. |

**Caching and determinism (CALC-8, CALC-9)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-C11 | "Byte-identical" needs a canonical serialization, which is not named. | Minor | RFC 8785 JSON canonicalization, plus the existing 1e-9° rounding. The cache key includes the profile content hash and the ephemeris data SHA. |

**Panchanga (PAN)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-PN1 | Sunrise inputs: place elevation, pressure and temperature for `rise_trans` are not specified. | Minor | Elevation from GeoNames (or 0, recorded). Refraction off per `hindu_rising`. |
| G-PN2 | PAN-3 conventions are undecided: samvatsara cycle (Jupiter-based north vs Chaitra-based south), naming of adhika and kshaya months, ritu (solar vs lunar), ayana (tropical vs sidereal solstice). | **Blocking** for PAN-3 (phase 4) | Profile fields and a reviewer decision. |

**Vargas (VAR)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-V1 | `ontology/vargas.yaml` holds "the declared construction", but its format is undefined. Uniform vargas follow a start-sign rule. D2 (Parashari hora), D30 (unequal parts) and others need tables. | **Blocking** for the varga engine | A data-driven spec: `{divisions: N, parts: equal \| [deg…], start: {rule: same \| by_parity \| by_modality \| table, …}, source}`. One engine interprets it. The same spec gives the boundary function for CALC-7. |

**Relationships and strength (REL, STR)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-R1 | REL-1 conventions are undecided: graha drishti sign-based or degree-based; node aspects (disputed 5/9); conjunction as same sign vs orb; where a dispositor chain ends (own sign, mutual cycle); parivartana subtypes. | **Blocking** for REL-1 | Profile fields `aspects.system`, `aspects.nodes`, `conjunction.mode` and `conjunction.orb`. Dispositor output = chain + terminal kind (`own_sign \| cycle`). |
| G-R2 | Functional benefic/malefic per lagna has no stated source: derived by rule or tabulated? Sources (BPHS, Laghu Parashari) disagree. | **Blocking** for DAS-5 | An ontology table: 12 lagnas × 9 grahas, roles, source. Do not derive it in code. |
| G-R3 | REL-3 lists edge properties in prose; no model exists. | Minor | A `Relation` model (§3.3). |
| G-S1 | Ashtakavarga: Lagna as a contributor, trikona/ekadhipatya shodhana and the kakshya order are not specified. | Minor (S, phase 4) | Spec plus ontology tables. Output keeps the pre-reduction and post-reduction tables. |
| G-S2 | Shadbala is one sentence. It has about 20 components with source variants. Chesta bala method, ayana bala declination basis, required rupas and Bhava Bala components are all unstated. | **Blocking** for STR-2 (phase 4) | A component spec with formulas, units, variant flags and sources (BPHS ch. 27), diffed per component against PyJHora. |

**Dashas (DAS)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-D1 | DAS-3 says "separate specifications" but defines no interface. Without one, every new system touches core code (NFR-9). | Minor now, **Blocking** for phase 7 | A `DashaSystem` protocol (§3.2). |
| G-D2 | The sandhi margin is "profile-defined" but has no field or value. | Minor | Profile field `dasha.sandhi_margin: {MD: days, AD: days}`. |
| G-D3 | The DAS-5 period-lord context has no schema. | Minor | A `PeriodLordContext` model holding fact IDs, not copied values. |
| G-D4 | *Found while building:* the dasha year length is a convention. The design says 365.2425; Jagannatha Hora and PyJHora default to the *true* sidereal year, measured per chart from the solar return. Boundaries then drift by up to about 14 h over 120 years. | Minor (within the 2-day tolerance) | `dasha.year_days` is provisional. With the mean sidereal year (365.256364) our AD starts match PyJHora to under a minute. A true-sidereal-year option can be added as a profile variant if the reviewer chooses it. |

**Transits (TRN)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-T1 | Under `nodes: true`, a 2-day step can miss the true node's short reversals. | Minor (KP only) | Step 6 h for the true node, or partition at its stations first. |
| G-T2 | Sun and Moon crossings are bracketed generically. Swiss Ephemeris already solves them exactly. | Minor | Use `swe.solcross_ut`/`swe.mooncross_ut` (sidereal flag) for Sun/Moon longitude events. Keep Brent for other bodies. |
| G-T3 | The aspect system for the double transit (TRN-3) and the eclipse contact orb (TRN-5) are not referenced. | Minor | Point to the profile's `aspects.system`. Add `eclipse.orb_deg`. |
| G-T4 | No location for the vedha pairs and kakshya tables (TRN-4). | Minor | `ontology/strength_tables.yaml`. |

**Method-specific (SCH)**

| ID | Gap | Severity | Proposed fix |
|---|---|---|---|
| G-B1 | SCH-BNN-1 geometry is clear. Which relations `bnn.linked` counts is a lineage decision. | Rules only | Reviewer decision when BNN cards are written. The geometry can be built now. |
| G-X1 | SCH-BNN-3 (lineage) is an ingestion and rule-card field, not a calculation. It is already covered (§9.7, §10.1). | — | Track under KNW/ING. |
| G-X2 | Phase-7 SCH items are one line each. | Expected | Each adapter writes a spec into design §7.10 at phase start. |

### 2.2 Proposed profile additions

All Blocking profile gaps in one place, in the YAML style of design §7.1:

```yaml
ayanamsa: {id: lahiri, swe_mode: SE_SIDM_LAHIRI, nutation: true}        # G-C4
nodes: {model: mean, retrograde: always}                                # G-C3
ephemeris: {…, coverage: {start_jd: …, end_jd: …}}                      # G-C1
dignity: {precedence: [exalted, moolatrikona, own, friend, neutral, enemy, debilitated],
          friendship_basis: compound}                                   # G-C5
graha_yuddha: {orb_deg: 1.0, bodies: […], winner: north_latitude}       # G-C6
gandanta: {arc_deg: 3.3333, source: …}                                  # G-C7
sandhi: {arc_deg: 1.0, source: …}                                       # G-C7
combustion: {measure: longitude, orbs: {…}}                             # G-C8
aspects: {system: parashari_sign, nodes: none}                          # G-R1
conjunction: {mode: same_sign}                                          # G-R1
dasha: {…, sandhi_margin: {MD: 180, AD: 15}}                            # G-D2
eclipse: {orb_deg: …}                                                   # G-T3
```

The values shown are placeholders. The reviewer picks them, matched to the JHora export settings so that NFR-1 fixtures compare like with like.

---

## 3. Modularity

### 3.1 What the design already gets right

- Features are pure functions of `(input, profile, engine version)` (§7).
- Method adapters are a protocol, and a new method needs "no change to core code paths" (§7.10).
- One root finder serves panchanga, transits and sensitivity (§7.8).
- Reference data lives in the ontology, not in code (KNW-11).

### 3.2 What is missing

| # | Missing piece | Why it matters | Proposal |
|---|---|---|---|
| M1 | **Ephemeris port.** Features call `swe` directly. | Swiss Ephemeris is AGPL (open question 4). A port keeps the licence decision local, lets tests use a stub, and lets Skyfield/JPL act as an independent oracle. | `Ephemeris` protocol: `position(body, jd, flags)`, `ascendant_and_cusps(jd, lat, lon, system)`, `ayanamsa(jd)`, `rise_set(…)`, `crossing(…)`, `eclipses(…)`, `coverage()`. One adapter, `SwissEphemeris`. |
| M2 | **Feature registry with dependencies.** `FeatureRequest` is referenced but not defined. Dependencies (dignity → friendship → positions; vargottama → D9) are implicit. | The planner, rule operators (`requires()`) and the cache need a common unit of work. Without one, the compute node becomes a large hand-ordered function. | `Feature` protocol: `id`, `requires: tuple[str, ...]`, `params` model, `compute(ctx, deps, params) -> FeatureResult`. The engine resolves requests into a DAG (stdlib `graphlib`), runs it once per chart and caches each node. |
| M3 | **Strategy registries for conventions.** | Every profile variant (ayanamsa, house system, aspect system, varga construction, sunrise, dasha system) is a switch point. Registries replace scattered `if profile.x == …` checks. Unknown keys become `unsupported_profile` in one place. | One registry per convention, keyed by the profile enum. |
| M4 | **`DashaSystem` protocol** | DAS-3 and NFR-9. | `id`, `eligible(chart) -> bool \| None`, `sequence(chart)`, `durations()`, `subdivide(period)`. Vimshottari is the first implementation. |
| M5 | **Result envelope.** `ChartFact` has no status. Unsupported features (`no_sunrise`, `out_of_range`, Placidus at the poles) have nowhere to live. | §6.2.5 and CALC-3 require feature-level status, with other features continuing. | `FeatureResult {feature_id, status: ok \| unknown \| unsupported \| failed, reason_code, facts, relations, periods, events, provenance}`. |
| M6 | **Read-only reference-data interface** | The calculation core should not depend on the whole ontology loader and its alias/canonicalizer code. | `ReferenceData` protocol: dignity ranges, friendship tables, dasha years, varga specs, bindu tables. The ontology loader implements it. |
| M7 | **Enforced layering** | Keeps `calc/` free of LangGraph, Qdrant, the store and LLM code, so it can become its own package (`astro-calc`) and be tested in isolation. | `import-linter` contracts in CI: `calc` imports nothing from `retrieval`, `workflows`, `store` or `llm`. The store plugs in through a `CachePort`. |
| M8 | **Plugin discovery for method adapters** | Phase-7 adapters ship without editing core. | `importlib.metadata` entry points (`astro.methods`). The `status: active` check stays in the core. |

### 3.3 Typed result models

`ChartFact.value: Any` loses checking at the rule-engine boundary. Use a Pydantic discriminated union on `kind` (`PositionValue`, `SignValue`, `HouseValue`, `DignityValue`, …), and add the two missing models:

```python
class Relation(BaseModel):                     # REL-3
    id: str; kind: Literal["aspect", "conjunction", "parivartana", "dispositor", "friendship", …]
    source: str; target: str                   # ontology IDs
    system: str                                # aspect system / friendship basis
    frame: str; counting: Literal["inclusive"]; direction: Literal["forward", "backward"]
    value: Any | None                          # e.g. aspect distance, friendship grade
    varga: str = "D1"; profile_id: str; sensitivity: …; provenance: dict

class TransitEvent(BaseModel):                 # TRN-2, TRN-3
    id: str; kind: Literal["ingress", "station", "conjunction", "contact", "return", "eclipse", "state"]
    body: str; target: str | None; start_utc: datetime; end_utc: datetime | None   # end for states
    motion: Literal["direct", "retrograde"] | None; profile_id: str; provenance: dict
```

### 3.4 Proposed layout of `src/astro/calc/`

```
calc/
  core/        angles.py  timescale.py  intervals.py  canonical.py  status.py
  ephemeris/   port.py  swiss.py  capability.py
  solver.py    bracket → Brent; stations; contacts (minimize |f|)
  profile.py   CalcProfile (Pydantic, closed enums) + strategy registries
  refdata.py   ReferenceData protocol
  model.py     ChartFact (typed), Relation, DashaPeriod, TransitEvent, FeatureResult
  engine.py    FeatureRequest → DAG → run → cache port
  features/    positions  condition  houses  relations  vargas  panchanga  ashtakavarga  shadbala  sensitivity
  dasha/       base.py (DashaSystem)  vimshottari.py
  transits/    positions  events  states  eclipses
methods/       parashari/  bnn/  (kp/ jaimini/ … via entry points)
```

---

## 4. Reuse: libraries, algorithms and patterns

### 4.1 Libraries

All are free. Licences were checked for the main runtime dependencies. The ones marked *verify* need checking before shipping.

| Need | Library | Licence | Use |
|---|---|---|---|
| Ephemeris, houses, ayanamsa, sunrise, eclipses, Sun/Moon crossings | **pyswisseph** 2.10.03 (Swiss Ephemeris) | AGPL-3.0 or commercial | Runtime engine (D6). Use built-ins rather than reimplementing: `calc_ut` with `FLG_SIDEREAL`, `houses_ex` (`W`, `S` = Sripati, `P`), `get_ayanamsa_ut`, `rise_trans` + `BIT_HINDU_RISING`, `solcross_ut`, `mooncross_ut`, `helio_cross_ut`, `sol_eclipse_when_glob`, `lun_eclipse_when`, `julday`/`revjul` with the Gregorian flag. Checked in this environment. |
| Independent position oracle | **Skyfield** + **jplephem**, JPL **DE440/DE441** kernels | MIT; kernels public domain | CI-only cross-check of geocentric positions over the long date range (DE441 covers −13200 to +17191). Not a runtime dependency. |
| Root finding, minimization | **SciPy** (`optimize.brentq`, `minimize_scalar(method="bounded")`) | BSD-3 | Refinement step of the solver (§7.8). |
| Vector math, unwrapping | **NumPy** (`unwrap`, vectorized sampling) | BSD-3 | Bracketing samples; Ashtakavarga tables. |
| Time zones | **zoneinfo** (stdlib) + **tzdata** (pinned) | Apache-2.0 | Fold/gap logic in §6.2 as designed. |
| Coordinates → IANA zone | **timezonefinder** | MIT | Coordinates-only input when no GeoNames hit (§6.2.2). |
| Gazetteer | **GeoNames** dump | CC BY 4.0 (attribution required) | Offline lookup; also supplies elevation for sunrise (G-PN1). |
| Fuzzy place matching | **RapidFuzz** | MIT | Ranking place candidates. |
| Calendar conversion | **convertdate** | MIT | Julian, Islamic, Hebrew, Persian, Indian national (Saka) to Gregorian, with provenance. Hindu lunisolar input dates have no reliable library, so request a verified conversion (already designed). |
| Models, validation, JSON Schema | **Pydantic** v2 | MIT | Profiles, facts, discriminated unions; schema export for CI. |
| YAML | **ruamel.yaml** | MIT | Round-trip loading keeps comments in reviewed files. |
| Canonical JSON | **rfc8785** | Apache-2.0 | Byte-identical re-runs and hashing (G-C11). |
| Dependency ordering | **graphlib** (stdlib) | PSF | Feature DAG (M2). |
| Layer enforcement | **import-linter** | BSD-2 | M7. |
| Property-based tests | **Hypothesis** | MPL-2.0 | Invariants (§4.3). |
| Snapshot / re-run tests | **pytest** + **syrupy** | MIT / Apache-2.0 | Byte-identical fixtures (CALC-9). |
| Test oracle for Indian features | **PyJHora** (and Jagannatha Hora exports) | *verify* | Diff panchanga, vargas, dashas, Ashtakavarga, Shadbala components. Never shipped (D6). |
| Panchanga algorithm reference | **drik-panchanga** | *verify* | Reference for tithi/nakshatra end-time solving and sunrise conventions. |

Not recommended:

- **json-logic** and similar rule engines: they have no three-valued (Kleene) logic and no `requires()` declarations, and the DSL is small (§10.2).
- **portion** (LGPL) for intervals: half-open UTC intervals need about 50 lines of own code.
- A general astrology framework at runtime (D6).

### 4.2 Standard algorithms to reuse

| Problem | Algorithm | Where |
|---|---|---|
| Event times (ingress, tithi end, nakshatra end) | Sample-and-bracket on unwrapped `f(t)`, then Brent's method. Exact Swiss Ephemeris crossings for Sun/Moon. | §7.4, §7.8 |
| Stations | Bracket sign changes of speed, then Brent on `speed = 0` | §7.8 |
| Grazing contacts near a station | Bounded scalar minimization of `\|f\|` on the station segment | §7.8 |
| All crossings of a retrograde loop | Partition at stations into monotone segments; at most one root per segment | TRN-2 |
| Birth-time sensitivity | The same solver run on the Lagna, cusp and Moon longitudes inside `[t − u, t + u]` | CALC-7 |
| Window segmentation (promise → period → trigger) | Sweep line over sorted boundary instants | APP-4 |
| Vimshottari | Recursive proportional subdivision, generated lazily to the requested depth | DAS-1 |
| Varga mapping | Data-driven: `part = floor(λ_in_sign / (30/N))`, then the spec's start-sign rule or table | VAR-1, VAR-2 |
| Ashtakavarga | Table lookup and summation (bitmask/NumPy), with reductions kept separate | STR-1 |
| Rule evaluation | Interpreter pattern over the DSL AST with Kleene logic | §10.3 |
| Determinism | Content-addressed caching: key = hash of canonical inputs + profile + engine | CALC-8, CALC-9 |

### 4.3 Property tests worth writing first

These need no expert data and catch most indexing errors:

- Tithi ∈ 1…30, karana ∈ 0…59 with the fixed-karana mapping, nakshatra ∈ 1…27, pada ∈ 1…4. Each index is constant between two consecutive solved boundaries.
- Dasha children exactly tile their parent: contiguous, half-open, durations sum to the parent within 1 s. The MD sequence follows the nine-lord order from the Moon's nakshatra lord.
- `active_chain(t)` is the unique chain whose periods contain `t`. `periods_in(w)` equals a brute-force overlap filter.
- Varga: D1 = identity; the Parashari D9 sign equals `floor(λ / (10/3)) mod 12` for sidereal longitude `λ` (an independent closed form for the table-driven engine); each varga part is contiguous.
- Retrograde loop: a target inside the loop's longitude range gets exactly three crossings, one outside it gets one, and each crossing lies in a distinct monotone segment.
- Same inputs and profile give identical canonical bytes (CALC-9).

---

## 5. Decisions needed

| # | Decision | Owner | Blocks |
|---|---|---|---|
| 1 | Ephemeris file set and coverage range (G-C1) | Operator | INP-1 acceptance, phase 1 |
| 2 | Node model and retrograde semantics; apparent vs true positions; dasha year length (G-C3, G-C12, G-C13, G-D4) | Reviewer, matched to JHora settings | NFR-1 fixtures (the code supports every option) |
| 3 | Dignity precedence and friendship basis; yuddha winner; gandanta and sandhi arcs (G-C5…G-C7) | Reviewer | CALC-2 |
| 4 | Aspect system, node aspects, conjunction definition (G-R1) | Reviewer | REL-1 |
| 5 | Varga spec format (G-V1) | Design | Varga engine |
| 6 | Functional-role table source (G-R2) | Reviewer | DAS-5 |
| 7 | Adopt the modularity additions M1–M8 into design §7 | Operator | Engine skeleton |
| 8 | Shadbala component spec (G-S2); PAN-3 conventions (G-PN2) | Reviewer + design | Phase 4 |

Once decisions 1, 2, 5 and 7 are made, layers L0–L2 and most of L3 can start, with condition and REL-1 following decisions 3 and 4.
