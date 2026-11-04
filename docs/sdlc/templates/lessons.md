---
id: YYYY-MM-short-slug
type: lesson
incident: <link to incident / channel thread / alert>
change: intent/<id>/      # the intent that carried the fix, if any
severity: sev1 | sev2 | sev3
---
# Lesson: <title>

## What happened
<Timeline with timestamps: detection (band/tier), first response, diagnosis, human authorisation, action, recovery.>

## Cause
<Root cause and the contributing factors. Cite evidence (diff, logs, metrics).>

## Fix
<What changed and where (PR link). Rollback used? Rehearsed when?>

## Verification
<Metric back inside its band: value, time, query/dashboard link.>

## Never again
- Regression test: `<path>`
- Eval case: `evals/cases/<file>.json`
- CLAUDE.md / skill / hook / band change: <link or "none">
