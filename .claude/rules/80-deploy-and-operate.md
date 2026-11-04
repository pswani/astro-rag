---
paths:
  - ".github/workflows/**"
  - "ops/**"
  - "deploy/**"
  - "lessons/**"
  - "runbooks/**"
---
# Rules for pipelines, deployment and operations (Stages 5–6)

- **O1 Up to the gate, never past it.** The agent prepares releases; a named release manager authorises production (hook: production gate). Everything the agent writes arrives as a PR.
- **O2 Autonomy is tiered by environment:** dev = agent deploys freely; staging = agent deploys, human notified; production = human authorises. Encode tiers in config, not prose.
- **O3 Pipelines start read-only.** New agent CI steps begin as judgment-only (triage, summarise, changelog). Write steps come later, behind existing gates.
- **O4 Sandboxed, scoped, identifiable.** Agent jobs run in containers with network policy, short-lived scoped tokens, no standing production credentials, under the agent's own identity.
- **O5 Deploy/status/rollback are tools** (MCP, per environment) — an allowlist, not a shell script holding credentials.
- **O6 Rollback is the most rehearsed path:** one command, exercised regularly in staging, before the agent may invoke it.
- **O7 Detection is deterministic:** version-controlled, unit-tested scripts (rolling baseline + Western Electric-style rules). No model decides whether a band is breached.
- **O8 Response tiers** (`ops/bands.yaml`): 1σ log only · 2σ diagnose read-only · 3σ propose a PR or trigger a pre-approved runbook. Nothing else.
- **O9 Findings re-enter the loop as intent.md** (`origin: monitor | incident`) with evidence, then flow through the normal stages and review gate.
- **O10 Every incident leaves a lesson and an eval:** `lessons/<YYYY-MM>-<slug>.md` (timeline, cause, fix, verification that the metric is back in band) plus a regression test and eval case.
