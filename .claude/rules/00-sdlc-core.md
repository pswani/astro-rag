# SDLC core rules (always apply)

Full process: `docs/sdlc/AI-NATIVE-SDLC.md`. Cite rule IDs (e.g. `G3`) in reviews, plans and findings.

## Track — pick one before starting (G0)
| Track | When | Artifacts required |
|---|---|---|
| **Full** | new capability, UX change, API/data-model change, anything risk class *elevated/high* | intent.md → spec.md → plan.md → PR |
| **Light** | bug fix or small change inside existing behaviour, risk *routine* | intent.md (may be the ticket/incident) → plan.md → PR |
| **Trivial** | typo, comment, docs-only, formatting | PR only |
When unsure, choose the heavier track and say why.

## Governance
- **G1 Artifact chain.** Each change lives in `intent/<NNNN-slug>/`. A stage starts by reading the previous artifact and ends by committing its own. Never skip a stage the track requires.
- **G2 Humans approve. Agents never:** set an artifact's `status: approved`, approve or merge a PR, push to a protected branch, deploy to production, or dismiss a review. The agent may act up to the gate and cannot pass it.
- **G3 Traceability.** Artifact frontmatter carries `id`, `parent`, `record` (external ticket ID, if any). Commits are titled `[<change-id>] <summary>`. PRs link intent, spec and plan.
- **G4 One source of truth per artifact**, as declared in `.sdlc/config.json` (`source_of_truth`). If it is a legacy tool (Jira, ServiceNow, requirements tool), read it at session start and write the outcome back in the same session; at minimum record the record ID in the artifact and the commit SHA in the record.
- **G5 Evidence, not assertion.** "Done", "passes", "fixed", "matches the mock" must be backed by pasted output from the toolchain (test run, build log, screenshot diff).
- **G6 Flag, don't decide.** Ambiguity, missing facts and contradicting policies become *Open questions* or *Flagged concerns* with a named owner. Never invent requirements, facts, numbers or policy interpretations.
- **G7 Scope discipline.** Change only what the approved plan lists. If reality differs, update plan.md in the same commit (enforced by hook).
- **G8 Risk class** (`routine | elevated | high`) is proposed in spec/plan and decides the approver: routine = engineer; elevated = tech lead; high (auth, payments, PII, migrations, infra, regulated code) = tech lead + named policy owner, and human line-by-line review.
- **G9 Secrets and data.** Never write credentials, tokens or real personal data into code, tests, fixtures, logs, artifacts or prompts. Use env vars / secret manager and synthetic data.
- **G10 Advisory vs deterministic.** A skill or rule is advisory. Anything that must always hold is backed by a hook, CI check or branch protection. When you notice a must-hold rule without one, flag it.
- **G11 Hooks are not obstacles.** When a hook blocks you, read its reason, follow the route it names, and never try to work around it (other tools, renamed paths, shell tricks).
- **G12 Learn once.** When the same mistake is corrected twice (by a human, a review or a hook), add the correction to CLAUDE.md/AGENTS.md in the same PR.
