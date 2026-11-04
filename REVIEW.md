# Review instructions
Used by AI review and the `pr-review` skill. Owner: Prashant Wani.

## Passes
Tag each finding with its pass:
- **Bugs:** logic errors, edge cases (date-line, DST gaps/overlaps, sign/nakshatra boundaries, 0/360 wrap), numeric precision, regressions.
- **Security & privacy:** birth data (date, time, place) never logged, sent off-machine, or left unencrypted; no network calls except the ephemeris fetch and an operator-enabled LLM API mode, which never receives raw birth data.
- **Compliance:** matches `intent/<id>/spec.md` and `plan.md`; the conventions in AGENTS.md (no LLM calculation, unknown-is-an-answer, attribute-never-blend, never substitute silently, reproducibility); `jyotish-evidence-rules` skill; `.claude/rules/` IDs.

## What Important means here
Wrong chart facts, a silent fallback or substitution, a lost `unknown`, blended schools, broken reproducibility, or birth data leaving the machine. Style and naming are Nits.

## Cap the nits
At most five; summarise the rest as a count.

## Do not report
Anything `ruff` or `lint-imports` already enforces (CI runs them).

## Machine-readable tally
End with `<!-- sdlc-review-tally: {"important": n, "nit": m} -->`.
