# AI-native SDLC — implementation reference

*This repo: changes live in `intent/<NNNN-slug>/`; baseline spec/design/plan are `docs/req/`, `docs/design/`, `docs/build/`.*

*For humans, Claude Code and Codex. Installed in each repo at `docs/sdlc/AI-NATIVE-SDLC.md`. Rules: `.claude/rules/` (IDs like G2, S5, T3). Based on Anthropic's AI-Native SDLC Playbook.*

## 1. The idea in five lines
1. Code is no longer the bottleneck; the human-speed steps around it are (requirements, review, release).
2. The line becomes a **loop**: Plan → Design → Build → Test → Deploy → Maintain → back to Plan.
3. **Every stage ends by committing an artifact the next stage starts by reading.** The chain of commits is the audit trail.
4. **Humans stay above the loop**: they instigate, direct and approve at the gates; agents do the work between gates.
5. **Skills make policy likely; hooks make violations close to impossible.** Anything that must always hold is deterministic.

## 2. The loop at a glance
| Stage | Input | Agent does (skill) | Output artifact | Human gate (approver) | Next trigger |
|---|---|---|---|---|---|
| 1 Plan | idea, ticket, incident | interviews like an analyst (`intent-capture`) | `intent.md` | product owner merges/accepts | intent approved |
| 2 Design | approved intent | applies policy skills, flags concerns (`spec-design`) | `spec.md` | PO (+ tech lead if elevated/high); policy owners resolve concerns | spec approved |
| 3 Build — plan | approved spec | plans in plan mode, gets interrogated (`implementation-plan`) | `plan.md` | engineer (tech lead if elevated/high) | plan approved |
| 3 Build — code | approved plan | implements with feedback loop (`build-and-verify`, `bugfix-test-first`) | commits + tests + evidence | — (guardrail hooks) | PR opened |
| 4 Test | the diff | self-verifies, `verifier` subagent, evals on config changes (`agent-evals`) | tool output in PR, CI checks | code owner reads evidence | checks green |
| 5 Deploy | PR | reviews (`pr-review`), fixes comments (`pr-babysit`), prepares release (`ci-cd-agent`) | review findings, release | code owner approves PR; release manager authorises prod | merge → pipeline |
| 6 Maintain | band breach, alert, channel message | diagnoses within tier, writes intent (`maintain-loop`) | `intent.md` (origin: monitor), lesson, eval | service owner triages | loop restarts at 1 |

## 3. Pick a track first (G0)
- **Full:** new capability, UX/API/data change, or elevated/high risk → intent → spec → plan → PR.
- **Light:** bug fix or small change in existing behaviour → intent (may be the ticket) → plan → PR.
- **Trivial:** typo, docs, formatting → PR only.

## 4. Where things live
```
intent/<NNNN-slug>/intent.md  spec.md  plan.md   # one folder per change
docs/sdlc/AI-NATIVE-SDLC.md   docs/sdlc/templates/          # this doc + templates
AGENTS.md (shared) · CLAUDE.md (= @AGENTS.md + Claude notes) · REVIEW.md
.claude/rules/  .claude/skills/  .claude/settings.json      # rules, policy skills, team settings
.sdlc/config.json  .sdlc/bin/sdlc_hooks.py  .sdlc/state/    # guardrail config, script, local state (gitignored)
evals/  ops/bands.yaml  ops/detect_bands.py  lessons/       # evals, control bands, post-mortems
```
Artifacts carry frontmatter `id, type, status, parent, record, risk, approved_by, approved_at`. Status: `draft → approved` (or `rejected` / `superseded`). **Only a named human sets `approved`.** Commits: `[<id>] <summary>`. Active change for guardrails: `echo <id> > .sdlc/state/active-change`.

## 5. Non-negotiables (agents and humans)
- No code before an approved plan. When code departs from the plan, update plan.md in the same commit.
- Agents never approve artifacts or PRs, never merge, never push to protected branches, never deploy to production. **The agent acts up to the gate and cannot pass it.**
- Evidence, not assertion: "done" carries pasted test/build/screenshot output.
- Bugs: failing test first, committed; then fix the code, never the test.
- Ambiguity and policy conflicts are flagged with an owner, never silently resolved or invented.
- No secrets or real personal data anywhere: code, tests, logs, artifacts, prompts.
- A mistake corrected twice goes into AGENTS.md/CLAUDE.md.
- When a guardrail blocks you, follow its route; never work around it.

## 6. Risk class decides the approver (G8)
| Class | Examples | Plan/spec approver | PR review |
|---|---|---|---|
| routine | small change, covered by tests | engineer | AI passes + code owner |
| elevated | new API, cross-team impact | + tech lead | + focused human review |
| high | auth, payments, PII, migrations, infra, regulated code | + tech lead + policy owner | human line-by-line |

## 7. Guardrails (deterministic layer)
| Guardrail | Where | Behaviour |
|---|---|---|
| Secrets in edits/commits | plugin hook + git pre-commit | block |
| Generated/frozen paths | hook (`protected_block`) | block |
| Agent/governance config (`.claude/settings.json`, hooks, workflows, REVIEW.md) | hook (`protected_ask`) | ask a human |
| Source edit without approved plan | hook (`plan_gate`) | ask (or block) |
| Artifact set to `approved` | hook | ask a human to confirm they are the approver |
| Migrations/infra without `CHANGE_TICKET` | hook | ask |
| Existing tests during a fix (`SDLC_FIX_MODE=1`) | hook | block |
| Commit with files not in plan.md (and plan not updated) | hook + git pre-commit | block |
| Commit/stop with unverified source changes | hook | block until verify command has run |
| Push to `main`/`release/*` | hook + branch protection | block |
| Production deploy without `RELEASE_APPROVAL` | hook (+ managed settings) | block |
| Format/lint after edit | hook (`format_commands`) | feedback to agent |
Non-negotiable controls belong in **managed settings** (see `managed-settings.example.json`), where engineers cannot switch them off.

## 8. Autonomy
- **Edits:** start with per-edit approval. Use auto-accept for routine work once CLAUDE.md, policy skills, hooks and tests are mature.
- **Parallel:** 2–3 worktree sessions per engineer (`claude --worktree <id>-<stream>`), only for plan workstreams that touch disjoint files. Add more only while review keeps up.
- **Environments:** dev = agent deploys; staging = agent deploys, humans notified; production = human authorises.
- **Maintain tiers:** 1σ log · 2σ read-only diagnosis · 3σ PR or pre-approved runbook only. Detection never uses a model.

## 9. Adoption order (prerequisites from the playbook)
| Start anytime (no prerequisites) | Needs | Then |
|---|---|---|
| Intent capture · CLAUDE.md · one policy skill · feedback loop · approval-gate hooks | intent + policy skills → **spec pass** | CLAUDE.md → **parallel sessions**; CLAUDE.md + feedback loop → **evals** |
| | intent/spec (+CLAUDE.md) → **plan mode** | CLAUDE.md + skills + subagents → **AI PR review** |
| | guardrails mature → **auto mode** | PR review + approval gates → **CI/CD**; intent + PR review + hooks + rollback → **maintain loop / on-call** |
Begin by prompting each step by hand. Codify it as a skill, then make the accepted artifact the trigger (CI on merge).

## 10. Measure it (from git, PRs, CI and incidents)
| Play | Leading | Lagging |
|---|---|---|
| Intent | idea → committed intent (hours) | intent survival rate; intent edits after spec |
| Spec | intent → spec commit (hours) | spec edits after first plan commit |
| Plan | first-pass merge share; plan approval → merge time | rework cycles; diff matches plan |
| CLAUDE.md | repeated mistakes | new joiner time to first merged PR |
| Skills | policy change → skill merged | review findings citing the policy → 0 |
| Feedback loop | first-pass CI success | review time per PR; change failure rate |
| Evals | pass rate trend; incident → eval time | regressions caught in CI vs production |
| PR review | time to first review; comments resolved without a human | defects/vulns before merge vs escaped |
| Gates | wait time per gate | gate violations reaching production |
| CI/CD | failures triaged without paging | DORA metrics |
| Maintain | breach → intent in queue | findings → merged fixes; repeat incidents |
`sdlc-trace` computes the git-derived ones.

## 11. Claude Code and Codex
| Need | Claude Code | Codex |
|---|---|---|
| Instructions | `CLAUDE.md` (imports `@AGENTS.md`) + `.claude/rules/` auto-loaded by path | `AGENTS.md`; read the matching `.claude/rules/<nn>-*.md` before writing each artifact |
| Skills | plugin `ai-native-sdlc` (`/ai-native-sdlc:<skill>`) | copy `skills/*` into your Codex skills folder (same `SKILL.md` format) |
| Plan before code | plan mode (Shift+Tab) | read-only/suggest approval mode; write plan.md first |
| Guardrails | plugin hooks (live, per action) | git pre-commit (`.sdlc/bin/sdlc_hooks.py git-pre-commit`) + Codex sandbox/approval policy + CI |
| Subagents | `agents/*.md` | run the same prompts as separate Codex tasks |
| Review / CI | claude-code-action, managed Code Review | same PR gates; any agent's PR gets the same review passes |

## 12. Legacy systems (G4)
For each artifact, name one source of truth. **Repo-first:** markdown is authoritative and the ticket links the commit. **Tool-first:** read the record at session start and write back via MCP in the same session. **Linkage (minimum):** artifacts hold the record ID and records hold the commit SHA.
