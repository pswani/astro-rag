# Calculation layer — requirements traceability

| | |
|---|---|
| **Date** | 2026-10-19 |
| **Scope** | Requirements §5.1 (inputs) and §5.2–§5.8, against design §6–§7 and the code on this branch |
| **Method** | Each requirement traced to its module and to the tests that show it; re-checked after review rounds 1–7 ([tasks.md](tasks.md) §D) |

**Status key**
- **Done**: implemented and tested.
- **Done (provisional)**: implemented; a convention it depends on is a provisional profile setting awaiting the reviewer ([calc-review.md](../design/calc-review.md) §5).
- **Partial**: the part that needs no decision is done; the rest is named.
- **Blocked**: needs an input or decision, which is named.
- **Later**: phase 7 or C items, not started by design.

## Inputs (INP)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| INP-1 | M/1 | Done | `normalize/birth.py`, `normalize/gazetteer.py` | Gregorian and Julian dates with conversion provenance; other calendars ask for a verified date; worldwide offline lookup, ambiguity asks; coordinates bypass lookup; place provenance recorded (`test_normalize.py`, `test_cli.py`, `test_condition_aspects.py::test_place_provenance_is_recorded`). The full GeoNames dump (alternate names, location IDs) is B4.5 |
| INP-2 | M/1 | Done | `normalize/birth.py` | Zones from the pinned `tzdata` package; DST gap → `invalid_local_time`, fold → both candidates; historical offsets labelled as assumptions; documented offsets accepted (`test_normalize.py`) |
| INP-3 | M/1 | Done | `normalize/birth.py`, `calc/features/*` | Precision → uncertainty defaults; unknown time = local noon ± 12 h, Lagna facts `unknown`, Moon-based facts assessed (`test_features.py::test_unknown_time_*`) |
| INP-5 | M/1 | Done | `methods/`, `cli/render.py` | Default method stated in every report (`test_cli.py::test_default_method_is_stated_and_sections_present`) |
| INP-8 | M/1 | Done | `methods/bnn/features.py` | No name, caste, religion or gender needed; `native_gender` optional, `unknown` without it (`test_transits_bnn.py`) |
| INP-4, INP-9 | M/1–2 | Later | — | Question handling belongs to the planner (design §11), outside the calculation layer |
| INP-6, INP-7 | S/7 | Later | — | Phase 7 |

## Calculation core (CALC)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| CALC-1 | M/1 | Done (provisional) | `features/positions.py`, `ephemeris/swiss.py` | Matches PyJHora within 10″ on 8 charts under matched conventions; apparent vs true positions and the node model are provisional (G-C12, G-C13) |
| CALC-2 | M/1 | Done (provisional) | `features/positions.py`, `features/condition.py`, `features/vargas.py` | Sign, degree, nakshatra, pada, lord, house; dignity, combustion, graha yuddha, gandanta, sandhi, vargottama (`test_condition_aspects.py`); orbs, arcs, winner rule and friendship basis are provisional (G-C5…G-C8) |
| CALC-3 | M/1 | Done | `calc/profile.py`, `ephemeris/swiss.py` | Lahiri, Raman, KP, True Chitra; whole-sign, Sripati, Placidus; mean/true nodes; unknown settings refused (`test_contracts.py`); Placidus above the polar circles → explicit `unsupported_feature` |
| CALC-4 | M/3 | Done | `features/houses.py` | Lagna, Chandra, Surya and any-graha frames with the frame recorded (`test_features.py`) |
| CALC-5 | S/7 | Later | — | Phase 7 |
| CALC-7 | M/3 | Done | `features/common.py` | Every discrete fact solved exactly over [t − u, t + u]; cross-and-recross is sensitive; a ground-truth test checks flags and margins against fine sampling for whole-sign, Sripati and Placidus (`test_sensitivity_ground_truth.py`, `test_features.py::test_cross_and_recross_near_station_is_sensitive`) |
| CALC-8 | M/1 | Done | `calc/engine.py` | On-demand features, cache keyed by inputs, profile, engine, ephemeris files and ontology (`test_engine.py`) |
| CALC-9 | M/1 | Done | `core/canonical.py` | Byte-identical across re-runs, the cache and a fresh process (`test_determinism.py`) |

## Panchanga (PAN)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| PAN-1 | M/1 | Done | `features/panchanga.py` | Five limbs with solved start and end; agrees with PyJHora on 8 charts |
| PAN-2 | M/1 | Done | `features/panchanga.py` | Hindu rising; birth before sunrise takes the previous vara; polar day/night → vara `unknown` with `no_sunrise` (`test_features.py`) |
| PAN-3 | S/4 | Blocked | — | Samvatsara, month naming, ritu and ayana conventions undecided (G-PN2) |
| PAN-4 | S/7 | Later | — | Phase 7 |

## Divisional charts (VAR)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| VAR-1 | M/1 | Done | `features/vargas.py`, `ontology/vargas.yaml` | D1/D9/D10 match PyJHora's Parashari method on 8 charts |
| VAR-2 | S/4 | Done (provisional sources) | same | All 13 remaining Shodashvarga from one data-driven spec; each matches PyJHora's traditional Parashari construction on 8 charts (`test_oracle_pyjhora.py::test_varga_signs`) |
| VAR-4 | S/7 | Later | — | Variants only when a rule family needs one |
| VAR-3 | C | Later | — | Not planned |

## Relationships and strength (REL, STR)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| REL-1 | M/1 | Done (provisional) | `features/relations.py`, `features/aspects.py` | Lordships, occupants, dispositor chains, parivartana, conjunctions, graha drishti with special aspects; drishti matches PyJHora on 8 charts; node aspects and conjunction mode are provisional (G-R1) |
| REL-2 | M/3 | Partial | `features/friendship.py` | Natural, temporal and compound friendship done; functional benefic/malefic per lagna is blocked on a sourced table (G-R2) |
| REL-3 | M/3 | Done | `calc/model.py` (`Relation`) | Edges carry system, frame, counting and direction; house aspects under cusp systems use their own `lagna_rashi` frame |
| STR-1, STR-2 | S/4 | Blocked | — | Ashtakavarga tables to transcribe (G-S1); Shadbala needs a component spec (G-S2) |
| STR-3 | C | Later | — | Not planned |

## Dashas (DAS)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| DAS-1 | M/1 | Done (provisional year) | `dasha/vimshottari.py` | MD/AD/PD tree, balance, year length recorded; AD starts match PyJHora to < 1 min with its mean sidereal year (G-D4) |
| DAS-2 | M/4 | Done | `dasha/vimshottari.py` | `active_chain`, `periods_in` checked against brute force (`test_features.py`) |
| DAS-4 | S/4 | Done (provisional margins) | `dasha/vimshottari.py` | Sandhi flags; boundary shifts for ±u; nakshatra change reported as a sequence change |
| DAS-5 | M/4 | Partial | `dasha/context.py` | Period-lord context holds fact and relation IDs (placement, lordships, dignity, combustion, war, aspects, conjunctions, relation to the MD lord); strength, functional role and karakatva are listed as `missing` |
| DAS-3 | S/7 | Later | — | Phase 7 |

## Transits (TRN)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| TRN-1 | M/4 | Done | `transits/positions.py` | Houses from natal Lagna and Moon, distances to natal points |
| TRN-2 | M/4 | Done | `transits/events.py`, `calc/solver.py` | Ingresses, stations, conjunctions, returns, grazing contacts; Saturn's three crossings of natal Mercury in 2026–27 (`test_transits_bnn.py`) |
| TRN-3 | M/4 | Done (provisional aspects) | `transits/states.py` | Sade Sati with phases, Ashtama, Kantaka, Jupiter from the Moon, Jupiter–Saturn double transit, Rahu–Ketu axis over natal points (`test_states_context_methods.py`) |
| TRN-5 | S/4 | Done (provisional orb) | `transits/eclipses.py` | Known 2024–27 eclipses found; natal contacts within the profile orb |
| TRN-6 | M/5 | Done | `methods/bnn/features.py` | Jupiter, Saturn and the nodes entering a natal planet's sign or trine |
| TRN-4 | S/4 | Blocked | — | Needs STR-1 and the vedha/kakshya tables |
| TRN-7 | C | Later | — | Not planned |

## Method-specific (SCH) and method adapters (design §7.10)

| ID | Pri/Ph | Status | Where | Evidence |
|---|---|---|---|---|
| SCH-BNN-1 | M/5 | Done | `methods/bnn/features.py` | Trines, 2nd, 12th, 7th, exchanges, conjunctions; retrograde-in-previous-sign variant (nodes excluded, recorded) |
| SCH-BNN-2 | M/5 | Done | `ontology/karaka_schemes.yaml` | BNN karaka roles apart from Parashari karakatva |
| SCH-BNN-3 | M/5 | Later | — | A lineage field on rule cards and passages (ingestion), not a calculation |
| Design §7.10 | — | Done | `methods/base.py`, `profiles/method/` | Method profiles, `MethodAdapter`, built-in registration plus entry-point plugins; readings need an `active` method, calculations may use a `draft` one (`test_states_context_methods.py`, `test_review_round2.py`) |
| SCH-JAI/KP/TAJ/PRS/MUH/CMP-1 | S/7 | Later | — | Phase 7 |
| SCH-LK-1, SCH-WES-1 | C | Later | — | Not planned |

## Design §6–§7 points checked

| Design point | Status |
|---|---|
| §6.2 order of checks: calendar → place → offset (gap before fold) → capability | As designed |
| §6.2.5 feature capability: no product date range; per-feature `out_of_range` | As designed; coverage is the installed ephemeris (1800–2400), and dates outside it exit 3 |
| §7.1 no Moshier fallback; pinned files | Return flags checked; the file actually read is verified after each call |
| §7.8 one root-finding engine; every loop crossing | `calc/solver.py`, used by every feature |
| §7.9 sensitivity by boundary solving, not sampling | Exact, value-based (`features/common.py`) |
| §7.11 cache key, determinism, NFR-1 tolerances | `test_engine.py`, `test_determinism.py`, `test_oracle_pyjhora.py` |

## Open decisions that limit "Done"

These are the reviewer's calls listed in [calc-review.md §5](../design/calc-review.md). The code supports every option, and each report lists the provisional settings in use:

- `position.apparent`, `nodes.model` and `nodes.retrograde`
- `dasha.year_days` and `dasha.sandhi_margin_days`
- `dignity.friendship_basis`, `combustion.orbs`, `graha_yuddha.winner`
- `gandanta.arc_deg`, `sandhi.arc_deg`
- `aspects.nodes`, `conjunction.mode`
- `eclipse.orb_deg`
