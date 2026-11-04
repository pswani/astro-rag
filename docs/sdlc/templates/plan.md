---
id: NNNN-short-slug
type: plan
status: draft            # draft | approved | superseded — engineer approves routine; tech lead elevated/high
parent: intent/NNNN-short-slug/spec.md   # or intent.md on the Light track
record: ""
risk: routine
author: Claude (planned with <engineer>)
approved_by: ""
approved_at: ""
---
# Plan: <title> (from spec.md <date>)

## Files that change
- `path/to/new_file.ext` — new: <reason>
- `path/to/existing.ext` — modify: <reason>
- `tests/test_thing.ext` — new: proves REQ-1, REQ-2

## Order of work
1. <step> — check: `<command>` → <expected result>
2. …

## Proof
| Requirement | Test(s) | How verified |
|-------------|---------|--------------|
| REQ-1 | `tests/test_thing.ext::test_x` | `make test` all green |
Verification commands: `make verify` (build + lint + tests) → "<healthy output>". UI: screenshot matches <mock>.

## Risks
- What could break:
- Riskiest step:
- External limits (rate limits, quotas, migrations, locks):
- Mitigation:

## Alternatives considered
- <option> — rejected because <…>

## Workstreams
- A (parallel-safe): steps 1–2, files <…>
- B (parallel-safe): step 3, files <…>
- Sequential: step 4 depends on A and B

## Rollback
<revert / feature flag / down-migration; how it was or will be rehearsed>

## Deviations
<Filled during build: what changed vs this plan and why (or "none").>
