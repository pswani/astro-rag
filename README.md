# astro — Vedic birth charts from the command line

`astro` computes a sidereal (Vedic) birth chart from a date, time and place of birth. It prints:

- South or North Indian charts, for any of the 16 divisional charts;
- planet positions with nakshatra and pada;
- dignity, combustion and other planetary conditions;
- aspects;
- the panchanga at birth;
- the Vimshottari dasha periods, including the one running now.

It runs entirely on your machine. It never guesses at an ambiguous input. And it tells you which parts of the chart could change if the recorded birth time is a few minutes off.

It is the calculation layer of the Jyotish agentic RAG project ([requirements](docs/req/requirements.md), [design](docs/design/design.md)). This guide is for people using the command; the [last section](#for-developers) is for contributors.

> **Status.** The calculations are verified (see [Accuracy](#accuracy-and-verification)). Several conventions that differ between sources (for example the mean or true lunar node) still await review by an astrologer. Every report lists them under **Notes**, and the [profile](#methods-profiles-and-provisional-settings) lets you change them.

---

## Contents

1. [Install](#install)
2. [Quick start](#quick-start)
3. [Giving the birth details](#giving-the-birth-details)
4. [Reading the report](#reading-the-report)
5. [Choosing what to show](#choosing-what-to-show)
6. [Methods, profiles and provisional settings](#methods-profiles-and-provisional-settings)
7. [JSON output](#json-output)
8. [Exit codes and messages](#exit-codes-and-messages)
9. [Accuracy and verification](#accuracy-and-verification)
10. [Troubleshooting and FAQ](#troubleshooting-and-faq)
11. [Privacy](#privacy)
12. [Configuration](#configuration)
13. [Data sources and licences](#data-sources-and-licences)
14. [Glossary](#glossary)
15. [For developers](#for-developers)

---

## Install

You need Python 3.11 or newer and about 2 MB for the ephemeris files. A network connection is needed only once, to download them.

```sh
git clone https://github.com/pswani/astro-rag.git
cd astro-rag
pip install -e ".[geo]"      # [geo] adds offline place names and time-zone lookup
astro ephemeris fetch        # downloads the Swiss Ephemeris files and checks their SHA-256
```

Check the installation:

```sh
astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN"
```

Without the `[geo]` extra, `astro` still works, but you must give coordinates and a time zone (`--lat`, `--lon`, `--tz`) instead of a place name.

---

## Quick start

```sh
astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN"
```

The start of the report:

```text
Method     parashari (default): Classical Vedic natal astrology (BPHS lineage), one declared profile [draft: calculations only, no reviewed rules yet]
Birth      1985-03-14 06:42 Asia/Kolkata (gregorian)   UTC 1985-03-14 01:12
Place      Pune, Maharashtra, India  18.5196N 73.8554E
Profile    parashari_v1: lahiri ayanamsa, whole sign houses, mean node
Ayanamsa   23.6468°   uncertainty ±2 min

+-----------+-----------+-----------+-----------+
|        Pi |        Ar |        Ta |        Ge |
|Me Ve(R)   |Ma Ra      |           |           |
|           |           |           |           |
+-----------+-----------+-----------+-----------+
|        Aq |                       |        Cn |
|As Su      |       Rasi (D1)       |           |
|           |                       |           |
+-----------+                       +-----------+
|        Cp |       1985-03-14      |        Le |
|Ju         |          Pune         |           |
|           |                       |           |
+-----------+-----------+-----------+-----------+
|        Sg |        Sc |        Li |        Vi |
|Mo         |Sa(R)      |Ke         |           |
|           |           |           |           |
+-----------+-----------+-----------+-----------+
```

…followed by the Navamsa (D9) and Dasamsa (D10) charts, then the tables described in [Reading the report](#reading-the-report).

More examples:

```sh
astro chart --date 1985-03-14 --time 06:42 --place "Pune, IN" --style north       # North Indian layout
astro chart --date 1990-07-15 --time 04:10 --lat -33.87 --lon 151.21              # coordinates
astro chart --date 1985-03-14 --place Pune                                        # birth time unknown
astro chart --date 1985-03-14 --time 06:42 --place Pune --varga-table all         # all 16 vargas
astro chart --date 1985-03-14 --time 06:42 --place Pune --method bnn              # Bhrigu Nandi Nadi
astro chart --date 1985-03-14 --time 06:42 --place Pune --json > chart.json       # for programs
astro places Springfield                                                          # look up a place
```

---

## Giving the birth details

### Date and calendar

`--date YYYY-MM-DD`. The date is Gregorian by default. For dates recorded in the Julian calendar (within the supported range, for example in Russia before 1918 or Greece before 1923), add `--calendar julian`. The conversion is recorded in the output.

Other calendars, such as Vikram Samvat or Shaka lunar dates, are not converted automatically, because a wrong conversion silently shifts the whole chart. Convert the date with a trusted source and give the Gregorian date.

The installed ephemeris covers **1800-01-01 to 2399-12-31**. A birth outside that range is refused (exit code 3); the program never falls back to a less accurate model without saying so.

### Time, precision and uncertainty

`--time HH:MM` or `HH:MM:SS` is the **local clock time** as recorded, without a UTC offset.

Recorded birth times are rarely exact, and a few minutes can change the rising sign (Lagna) and everything that depends on it. Tell `astro` how precise the time is, and it will mark every fact that could change within that margin:

| `--precision` | Meaning | Uncertainty used |
|---|---|---|
| `minute` (default) | recorded to the minute | ±2 min |
| `rounded_5` | rounded to 5 minutes ("6:45") | ±3 min |
| `rounded_15` | rounded to a quarter hour | ±8 min |
| `hour` | known to the hour | ±30 min |

Or set the margin yourself with `--uncertainty MINUTES` (0–720).

**Unknown birth time.** Leave out `--time`. The chart is computed for local noon with an uncertainty of ±12 hours:

- The Lagna and the houses counted from it are shown as unknown.
- The North Indian chart uses the Moon's sign as the first house (*Chandra lagna*), and its caption says so.
- Moon-based facts are still given, each marked if it could change during the day.

### Place

**By name:** `--place "City[, State][, Country]"`.

```sh
--place Pune
--place "Pune, IN"
--place "Springfield, Illinois"
--place "London, UK"
--place "São Paulo, BR"
```

- **Matching:** names are case- and accent-insensitive (`Sao Paulo` finds São Paulo). The country can be an ISO code (`IN`, `GB`, `US`), a country name, or a common short form (`UK`, `USA`, `UAE`). The state can be written in full or as its first letters (`Springfield, Ill`).
- **Two places with the same name:** `astro` never picks one for you. It lists the candidates and stops, so you can be specific:

  ```text
  "Springfield" matches several places; add the state and country, or give the coordinates:
    --place "Springfield, Missouri, US"   or   --lat 37.2153 --lon -93.2982
    --place "Springfield, Massachusetts, US"   or   --lat 42.1015 --lon -72.5898
    …
  ```

- **Spelling mistakes:** close matches are suggested (`Chenai` → Chennai, Tamil Nadu, India).
- **Older or alternative names** (such as *Bangalore*) are not in the offline table. Use the current official name (*Bengaluru*), or coordinates.
- **What is in the table:** about 155,000 places with 1,000 or more inhabitants, from GeoNames. For a smaller village, use coordinates. `astro` never substitutes the nearest town.

**By coordinates:** `--lat` and `--lon` in decimal degrees (north and east positive). For example, Sydney is `--lat -33.87 --lon 151.21`. The time zone is then looked up from the coordinates (this needs `[geo]`), or you can give it with `--tz`.

**Elevation** (`--elevation METRES`) only affects sunrise, and so the weekday (vara) of a birth close to sunrise.

To check how a name resolves before computing a chart:

```sh
astro places "Springfield, US"
```

### Time zone and daylight saving time

You give the clock time; `astro` converts it to universal time using the time-zone rules **in force on that date at that place**, including historical changes and daylight saving time. You normally don't need to do anything.

There are two exceptions, each about one hour a year. In both, the date and clock time alone don't identify a single moment, so `astro` asks:

- **When clocks go back**, an hour of clock times happens twice. "01:30" on 7 Nov 2021 in New York could be 05:30 or 06:30 UTC:

  ```text
  ambiguous_local_time: 2021-11-07 01:30:00 occurs twice in America/New_York (DST fold)
  choose the clock reading with one of:
    --utc-offset=-04:00   (= 2021-11-07 05:30 UTC)
    --utc-offset=-05:00   (= 2021-11-07 06:30 UTC)
  ```

  Re-run with the right one; the birth record or the family will usually know whether it was before or after the change. Use the `=` form, as shown, so that the minus sign isn't read as an option.
- **When clocks go forward**, an hour of clock times never happens (02:30 on 14 Mar 2021 in New York). `astro` reports `invalid_local_time` (DST gap); check the recorded time and date.

An hour matters: the Lagna moves about 15° an hour, which usually changes the rising sign, every house and the dasha dates.

**Historical births and documented standards.** For older births, the offset comes from the time-zone database's history. The report notes that this is an assumption about which clock was actually used. If a document states the standard (for example "Madras time", UTC+05:21, or a local mean time), give it directly:

```sh
astro chart --date 1890-06-01 --time 06:42 --place Pune --utc-offset +05:21
```

`--utc-offset` applies no daylight-saving rule. It replaces `--tz`; don't give both.

---

## Reading the report

### Header

```text
Method     parashari (default): Classical Vedic natal astrology … [draft: calculations only, no reviewed rules yet]
Birth      1985-03-14 06:42 Asia/Kolkata (gregorian)   UTC 1985-03-14 01:12
Place      Pune, Maharashtra, India  18.5196N 73.8554E
Profile    parashari_v1: lahiri ayanamsa, whole sign houses, mean node
Ayanamsa   23.6468°   uncertainty ±2 min
```

- **Method:** the astrological school (Parashari unless you choose another). *Draft* means the calculations can be used but no interpretation rules have been reviewed yet.
- **Birth:** the clock time and time zone you gave, and the universal time actually used.
- **Profile:** the calculation conventions; see [Methods, profiles and provisional settings](#methods-profiles-and-provisional-settings).
- **Ayanamsa:** the offset between the tropical and sidereal zodiacs on that date.

### Marks used throughout

| Mark | Meaning |
|---|---|
| `*` | This fact changes somewhere within the birth-time uncertainty, e.g. the Lagna is a few minutes from the next sign. |
| `?` | This fact cannot be known, e.g. the Lagna's house when the birth time is unknown. |
| `(R)` | Retrograde (apparently moving backwards). Rahu and Ketu always move backwards and are not marked. |
| `(r)` | In the BNN section: a link that exists only through the retrograde-in-previous-sign rule. |

Example with `--precision rounded_15` (±8 minutes): the Lagna could fall in the next sign, and the Sun's house would then change.

```text
As Lagna   Aquarius*    28°01′34″*  Purva Bhadrapada 3   Jupiter      1
Su Sun     Aquarius     29°45′28″   Purva Bhadrapada 3   Jupiter     1*
```

### The charts

**South Indian layout** (`--style south`, the default): each square is a **sign**, always in the same place. Pisces is at top left and the signs run clockwise. Each square shows its sign's abbreviation at top right and the planets in that sign. `As` marks the Lagna.

| Abbr. | Sign | Abbr. | Sign | Abbr. | Sign |
|---|---|---|---|---|---|
| Ar | Aries (Mesha) | Le | Leo (Simha) | Sg | Sagittarius (Dhanu) |
| Ta | Taurus (Vrishabha) | Vi | Virgo (Kanya) | Cp | Capricorn (Makara) |
| Ge | Gemini (Mithuna) | Li | Libra (Tula) | Aq | Aquarius (Kumbha) |
| Cn | Cancer (Karka) | Sc | Scorpio (Vrishchika) | Pi | Pisces (Meena) |

Planets: `Su` Sun, `Mo` Moon, `Ma` Mars, `Me` Mercury, `Ju` Jupiter, `Ve` Venus, `Sa` Saturn, `Ra` Rahu, `Ke` Ketu, `As` Lagna.

**North Indian layout** (`--style north`): each region is a **house**, always in the same place. House 1 is the top centre diamond, and houses run anticlockwise. The number in each house is its **sign number** (1 = Aries … 12 = Pisces). If a small triangle is too full, it shows `+n more`; the tables always list everything.

```text
Navamsa D9
+-----------------------------------------------------------+
| \                         /   \                         / |
|    \         4         /         \         2         /    |
|      \               /             \     Mo Ma     /      |
|         \         /                   \   Ju    /         |
|           \     /           3           \     /           |
|     5       \ /         As Su Ke          \ /       1     |
…
```

Here Gemini (3) rises in the Navamsa; house 12 holds Taurus (2) with the Moon, Mars and Jupiter.

**Divisional charts (vargas).** By default you get the Rasi (D1), Navamsa (D9) and Dasamsa (D10). Any of D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45 and D60 can be drawn with `--vargas`. Each uses one declared Parashari construction, listed in `ontology/vargas.yaml`.

### Planet table

```text
Body       Sign         Degree      Nakshatra            Lord     House R
As Lagna   Aquarius     28°01′34″   Purva Bhadrapada 3   Jupiter      1
Mo Moon    Sagittarius  03°43′34″   Mula 2               Ketu        11
Sa Saturn  Scorpio      04°26′37″   Anuradha 1           Saturn      10 R
```

- **Degree:** the position within the sign, in degrees, minutes and seconds.
- **Nakshatra:** the lunar mansion and its pada (quarter, 1–4).
- **Lord:** the nakshatra's ruling planet.
- **House:** counted from the Lagna under the profile's house system.
- **R:** retrograde.

### Dignity and condition

```text
Body       Dignity        Condition                Aspected by    Conjunct
Su Sun     Neutral        sandhi                   -              -
Ma Mars    Moolatrikona   -                        -              Ra
Ju Jupiter Debilitated    -                        Sa             -
Ve Venus   Exalted        gandanta                 -              Me
Sa Saturn  Great enemy    -                        Ma             -
```

- **Dignity**, strongest first:
  - **Exalted**, **Moolatrikona**, **Own sign**;
  - then the planet's relationship to the lord of the sign it occupies: **Great friend**, **Friend**, **Neutral**, **Enemy**, **Great enemy**;
  - **Debilitated**.

  Rahu and Ketu have no dignity here, because sources disagree.
- **Condition:**
  - **combust** (too close to the Sun; the distance is shown);
  - **war won/lost** (graha yuddha: two planets within 1°);
  - **gandanta** (at a water–fire sign junction);
  - **sandhi** (within 1° of a sign boundary).
- **Aspected by:** the planets casting a full aspect (graha drishti) on this one. All planets aspect the 7th sign from themselves; Mars also the 4th and 8th, Jupiter the 5th and 9th, Saturn the 3rd and 10th.
- **Conjunct:** planets in the same sign.

### Aspects cast

```text
Ma Mars    Cn, Li, Sc  houses 6, 9, 10
Sa Saturn  Cp, Ta, Le  houses 12, 4, 7
```

The signs each planet aspects, and the houses those signs are counted from the Lagna.

### Varga signs

With `--varga-table` (default: the charts drawn), a table of each body's sign in each divisional chart, followed by the bodies that are *vargottama* (in the same sign in D1 and D9). `--varga-table all` lists all 15 divisions after D1.

### Panchanga at birth

```text
Vara       Wednesday              (from sunrise 1985-03-13 06:48)
Tithi      Krishna Ashtami (Krishna paksha)     ends 1985-03-14 10:37
Nakshatra  Mula                                 ends 1985-03-15 00:01
Yoga       Vyatipata                            ends 1985-03-15 04:51
Karana     Kaulava                              ends 1985-03-14 10:37
```

The five limbs of the Hindu day, with their end times in local time. The **vara** (weekday) starts at **sunrise**, not midnight. This example birth is at 06:42, six minutes before sunrise on 14 March, so it is still **Wednesday** (13 March).

### Vimshottari dasha

```text
Balance at birth: Ketu 5.04 years
  Ketu     1983-03-30 → 1990-03-30
  …
  Mars     2026-03-30 → 2033-03-29   ◀ now
Current (2026-10-19): Mars / Rahu / Rahu until 2026-10-22
  MD Mars     in house 3; rules 3, 10; moolatrikona
  AD Rahu     in house 3; 1 from the MD lord
Dasha dates shift by +3.6 / -3.6 days if birth was 2 min earlier / later
```

- **The periods:** the major periods (mahadasha) over 120 years, from the Moon's nakshatra at birth.
- **Current:** the major, sub- and sub-sub-period (MD / AD / PD) running now. Use `--as-of 2030-01-01T00:00+00:00` to see another date.
- **Period lords:** for each, where it sits, which houses it rules and its dignity.
- **Shift:** how far all dasha dates move per the birth-time uncertainty. With an uncertain time they can move by weeks.
- **Sandhi:** if the chosen date is close to a period boundary, a sandhi line says so.

### BNN section (`--method bnn`)

For Bhrigu Nandi Nadi this section lists, for each planet, the planets with it, in its 5th and 9th (trines), 2nd, 12th and 7th signs. It also shows the native's karaka. Give `--native-gender male` (Jupiter) or `female` (Venus) to set it; it is never assumed.

### Notes

The **Notes** section lists:

- assumptions made (for example a historical time-zone offset);
- the provisional settings in use;
- anything that could not be computed, and why.

Read it before relying on a chart.

---

## Choosing what to show

| Option | Effect |
|---|---|
| `--style south\|north` | Chart layout (default `south`). |
| `--vargas D1,D9,…` | Which divisional charts to draw (default `D1,D9,D10`). |
| `--varga-table D2,D30,…\|all` | Which divisions to list in the varga table (default: the charts drawn). |
| `--as-of 2030-01-01T00:00+00:00` | The moment for the "current" dasha (default: now). A UTC offset is required. |
| `--method parashari\|bnn` | Astrological school (default `parashari`). |
| `--profile ID` | Calculation profile (default: the method's own). |
| `--native-gender male\|female` | Optional input used only by BNN. |
| `--json` | Machine-readable output instead of the report. |

---

## Methods, profiles and provisional settings

A **method** is an astrological school. A **profile** is a named, versioned set of calculation conventions. Both are plain YAML files you can read:

| Method | File | Default profile |
|---|---|---|
| Parashari (BPHS lineage) | `profiles/method/parashari.yaml` | `parashari_v1` |
| Bhrigu Nandi Nadi (R. G. Rao) | `profiles/method/bnn.yaml` | `bnn_v1` (adds the retrograde-in-previous-sign rule) |

The calculation profile `profiles/calc/parashari_v1.yaml` fixes, among other things:

| Setting | Value in `parashari_v1` | Alternatives |
|---|---|---|
| Ayanamsa | Lahiri | Raman, Krishnamurti, True Chitra |
| House system | whole sign | Sripati, Placidus |
| Lunar node | mean | true |
| Positions | apparent | true (geometric) |
| Dasha year | 365.2425 days | any length, e.g. 365.256364 (sidereal) |
| Sunrise | centre of the disc, no refraction (Hindu rising) | upper limb with refraction |
| Combustion orbs | Moon 12°, Mars 17°, Mercury 14° (12° retrograde), Jupiter 11°, Venus 10° (8° retrograde), Saturn 15° | any |
| Graha yuddha | within 1°; the more northern planet wins | lesser longitude wins |
| Gandanta, sandhi | 3°20′ and 1° | any arc |
| Node aspects | none | 7th only; 5th, 7th and 9th |
| Conjunction | same sign | within an orb |

**Provisional settings.** Sources and software disagree on several of these, and the project's reviewer has not yet fixed them. They are listed under `provisional:` in the profile and in every report's Notes. They explain most differences from other software; see the [FAQ](#troubleshooting-and-faq).

**Changing a convention.** Profiles are immutable once used: a chart is always traceable to the exact conventions behind it. Don't edit `parashari_v1`. Copy it to a new file, for example `profiles/calc/parashari_v2.yaml`, set `id: parashari_v2`, change what you need, and add the new ID to the method's `calc_profiles` list. Then:

```sh
astro chart … --profile parashari_v2
```

Unknown settings or values are refused with `unsupported_profile`; a profile is never half-applied.

---

## JSON output

`--json` prints everything the report is built from:

```text
input           the arguments as given
place           the matched place (name, state, country, coordinates)
normalization   status, the UTC instant, provenance (calendar, time zone, offset, place) and assumptions
method          the method profile
profile         the full calculation profile
chart_id        an ID for this chart (see Privacy)
as_of           the instant used for the current dasha
results         one entry per calculation: positions, houses, relations, friendship, condition,
                aspects, vargas, panchanga, vimshottari, dasha_active, dasha_context
```

Each result has a `status` (`ok`, `unknown`, `unsupported`, `failed`) with a `reason` code, and contains:

- `facts`: one value each, e.g. the Sun's sign:

  ```json
  {"kind": "sign", "subject": "graha:sun", "value": "rashi:aquarius", "frame": null, "varga": "D1",
   "sensitivity": "stable", "margin_minutes": [null, null], "profile_id": "parashari_v1", …}
  ```

  `sensitivity` is `stable`, `sensitive` (with `margin_minutes`: how many minutes earlier and later the birth would have to be for the value to change) or `unknown` (then `value` is `null`). `frame` says what a house is counted from (`lagna`, `chandra`, `surya`, `graha:…`). `varga` names the divisional chart.
- `relations`: typed links between bodies, such as aspects, conjunctions, sign exchanges, dispositors, friendships, wars and BNN links. Each records its system and counting convention.
- `periods`: dasha periods with UTC start and end (end excluded).

Identifiers are stable names, such as `graha:saturn`, `rashi:libra`, `nakshatra:mula`, `bhava:10` and `tithi:krishna_ashtami`.

Example (needs [`jq`](https://jqlang.github.io/jq/)):

```sh
astro chart --date 1985-03-14 --time 06:42 --place Pune --json |
  jq '.results.positions.facts[] | select(.kind=="sign") | {subject, value, sensitivity}'
```

---

## Exit codes and messages

| Code | Meaning | Typical causes |
|---|---|---|
| 0 | Chart produced | — |
| 1 | Setup problem | Ephemeris files missing (`astro ephemeris fetch`), files not found (`ASTRO_HOME`), invalid `ASTRO_CHART_KEY` |
| 2 | More input needed | Ambiguous or unknown place, DST fold or gap, invalid date, unknown calendar, unknown profile, method or varga, malformed option |
| 3 | Unsupported | Birth outside the ephemeris range; a profile that does not belong to the chosen method |

Messages start with a reason code (`ambiguous_local_time`, `invalid_local_time`, `out_of_range`, `unsupported_calendar`, …) followed by a sentence saying what to do.

---

## Accuracy and verification

- **Astronomy.** The calculations use the Swiss Ephemeris (the same engine as most astrology software) with pinned data files. If a date is outside the files, `astro` refuses rather than quietly switching to the built-in lower-accuracy model.
- **Checked against PyJHora** on eight charts (both hemispheres; Asian, European and American time zones; 1850 to 2120), with matching conventions:
  - planet positions within 10″ and the Lagna within 30″;
  - all five panchanga limbs and the vara;
  - all 16 divisional charts under the traditional Parashari construction;
  - graha drishti;
  - the start of every Vimshottari sub-period, within a minute.
- **Birth-time sensitivity** is solved exactly at the instants where a fact can change, not by sampling. A test re-computes every fact on a 2-minute grid across the uncertainty window and checks both the `*` marks and the margins.
- **Determinism.** The same input and profile give byte-identical output on every run with the same versions of the software and data files.

**Known limits:**

- Births before 1800 or after 2399 need additional ephemeris files and a profile that lists them.
- Older place names need the full GeoNames data, which is not bundled yet.
- The provisional conventions above.
- Lunar-month names, samvatsara, Ashtakavarga and Shadbala are not computed yet.

---

## Troubleshooting and FAQ

**"no place named …"**
Try the current official name, add the country, or give coordinates. `astro places NAME` shows what the table knows.

**"… matches several places"**
Add the state and/or country from the list shown, or use the coordinates printed next to each candidate.

**"… occurs twice … (DST fold)" or "… does not exist … (DST gap)"**
See [Time zone and daylight saving time](#time-zone-and-daylight-saving-time).

**"out_of_range: the installed ephemeris covers 1800-01-01 until 2400-01-01"**
The birth is outside the bundled ephemeris files.

**`astro ephemeris fetch` fails with "CERTIFICATE_VERIFY_FAILED"**
Python could not verify the download server's TLS certificate. `astro` already trusts the `certifi` bundle as well as the system store, so this usually means a proxy or antivirus re-signs HTTPS traffic with its own certificate. Point Python at that certificate with `export SSL_CERT_FILE=/path/to/ca.pem`. On macOS with Python from python.org, also run `/Applications/Python 3.x/Install Certificates.command` once. Make sure you are running a version of `astro` that includes this fix (`git pull`, then `pip install -e ".[geo]"`).

**"ephemeris_unavailable … run `astro ephemeris fetch`"**
The data files are missing or damaged. Run the command; if you keep them elsewhere, set `ASTRO_EPHE`.

**Why does the report say Wednesday for a birth on a Thursday morning?**
The Hindu day runs from sunrise to sunrise. A birth before sunrise belongs to the previous vara.

**Why is Rahu about 1–1.5° different from another program?**
`parashari_v1` uses the **mean** node; many programs default to the **true** node. Both are legitimate; create a profile with `nodes: {model: true, retrograde: by_speed}` to match.

**Why are planets about 20″ (the Sun) different from another program?**
Apparent positions (as seen, including the effects of light travel) versus true geometric positions. Set `position: {apparent: false}` in a new profile to use geometric positions.

**Why do my dasha dates differ by a few hours or a day from Jagannatha Hora?**
The length of a dasha year is a convention. `parashari_v1` uses 365.2425 days, while Jagannatha Hora defaults to a sidereal year measured from the chart itself. Over a lifetime this moves dates by up to about a day.

**Why does D10 (or D3, D30…) differ from another program?**
Several constructions exist for most divisional charts. `astro` uses one declared Parashari construction for each (`ontology/vargas.yaml`). Other programs sometimes default to *parivritti* (cyclic) variants.

**Why are some facts marked `*` although I know the birth time?**
Every recorded time is assumed to carry the uncertainty of its precision (±2 minutes for `minute`). Use `--uncertainty 0` if the time is truly exact.

---

## Privacy

Everything runs locally; no birth data leaves your machine. The `chart_id` in JSON output is derived with a secret key, so it cannot be traced back to the birth details. By default the key is random for each run. Set `ASTRO_CHART_KEY` to a secret of at least 32 hex digits (64 recommended, e.g. from `python -c "import secrets; print(secrets.token_hex(32))"`) to get the same ID for the same chart across runs.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ASTRO_HOME` | the checkout containing `ontology/` and `profiles/` | Where the curated data lives |
| `ASTRO_EPHE` | `$ASTRO_HOME/data/ephe` | Where the Swiss Ephemeris files live (`astro ephemeris path` prints it) |
| `ASTRO_CHART_KEY` | random per run | Key for stable chart IDs (at least 32 hex digits) |

---

## Data sources and licences

- **Swiss Ephemeris** (Astrodienst) via `pyswisseph`: AGPL-3.0 or a commercial licence. This project is licensed AGPL-3.0-or-later accordingly.
- **Place names:** [GeoNames](https://www.geonames.org/) (CC BY 4.0), via the `reverse_geocode` package. Reports that use a place name carry the attribution.
- **Time zones:** the IANA time-zone database (`tzdata`), pinned to the version named in the profile.
- **Reference tables** (sign lords, dignities, nakshatras, dasha years, varga constructions): `ontology/*.yaml`, following BPHS, marked provisional until reviewed.
- **PyJHora** is used only in tests, to verify results; it is not part of the program.

---

## Glossary

| Term | Meaning |
|---|---|
| Lagna | The rising sign (ascendant); the first house in most systems |
| Rasi (D1) | The birth chart proper |
| Navamsa (D9), Dasamsa (D10)… | Divisional charts: each sign divided into N parts, each mapped to a sign |
| Vargottama | The same sign in D1 and D9 |
| Nakshatra, pada | One of 27 lunar mansions of 13°20′, and its quarter (3°20′) |
| Graha drishti | A planet's aspect on a sign and the planets in it |
| Dignity | How well placed a planet is by sign: exalted … debilitated |
| Moolatrikona | A planet's "office" range within one of its signs |
| Combust | Too close to the Sun to be effective |
| Graha yuddha | Planetary war: two planets within 1° |
| Gandanta | The junction of a water and a fire sign (end of Cancer/Scorpio/Pisces) |
| Sandhi | The edge of a sign |
| Tithi, karana, nitya yoga, vara | Lunar day, half lunar day, Sun–Moon yoga, weekday: with the nakshatra, the five panchanga limbs |
| Vimshottari dasha | The 120-year planetary period system; MD/AD/PD = major, sub- and sub-sub-period |
| Dasha sandhi | The junction between two periods |
| Ayanamsa | The offset between the tropical and sidereal zodiacs |
| BNN | Bhrigu Nandi Nadi, as published by R. G. Rao |

---

## For developers

```sh
pip install -e ".[dev,oracle]"
python scripts/fetch_ephemeris.py
ruff check src tests scripts && lint-imports && pytest
```

- **Code:** `src/astro/`
  - `calc/`: the deterministic calculation layer; features, solver, ephemeris adapter, profiles.
  - `normalize/`: birth input, time zones, places.
  - `methods/`: method adapters.
  - `cli/`: this command.
- **Curated data:** `ontology/`, `profiles/`.
- **Build documents:** [task list](docs/build/tasks.md), [design notes](docs/build/design-notes.md), [requirements traceability](docs/build/alignment.md), [calculation review and open decisions](docs/design/calc-review.md).
- **Import rules:** `lint-imports` enforces them. The calculation layer never imports the CLI, normalizer or methods, and only the Swiss Ephemeris adapter imports `swisseph`.
