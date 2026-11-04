---
paths:
  - "tests/**"
---
# Rules for tests (Stage 4 — Test)

- **T1 Every requirement is proven.** Each `REQ-n` in spec.md has at least one test named or commented with its ID.
- **T2 Bugs: failing test first.** Reproduce the bug as a test, run it, confirm it fails *for the expected reason*, commit it, then fix the code. Skill: `bugfix-test-first`.
- **T3 Never weaken the check.** Do not delete, skip, loosen assertions, raise tolerances or update snapshots/goldens to make a failure pass. Fix the code. If the test is wrong, stop and say so. (Fix mode locks existing tests by hook.)
- **T4 Deterministic.** No real network, wall-clock or random dependence without control; no order dependence. Flaky tests are quarantined with a ticket, not retried silently.
- **T5 Synthetic data only.** No production data or real personal data in fixtures (G9).
- **T6 Cover the edges** the spec names: error paths, authorisation failures, limits, empty/large inputs.
- **T7 UI work closes the loop visually:** implement → screenshot → compare with the approved mock → adjust (typically 2–3 rounds); attach the final screenshot.
- **T8 Incidents become permanent tests:** every production incident fix adds a regression test and an eval case (`evals/cases/`).
