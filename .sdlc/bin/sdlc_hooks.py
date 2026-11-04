#!/usr/bin/env python3
"""AI-native SDLC guardrails: the deterministic layer behind the skills.

Usage:  sdlc_hooks.py <event>        (Claude Code hook JSON on stdin)
        sdlc_hooks.py git-pre-commit (run from .git/hooks/pre-commit; works for any agent or human)
        sdlc_hooks.py doctor         (print resolved config and active change)

Events: pre-edit | pre-bash | post-edit | post-bash | stop | git-pre-commit | doctor

Inert unless the project has .sdlc/config.json. Standard library only. Every check is
fast and scoped to the file or command at hand; heavy checks belong in CI.

Decisions:  deny -> exit 2, reason on stderr (Claude sees it and the route to approval)
            ask  -> PreToolUse JSON permissionDecision "ask" (a named human decides;
                    in headless runs an ask cannot be answered, so it fails closed)
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

DEFAULTS = {
    "changes_dir": "docs/changes",
    "source_globs": ["src/**", "app/**", "lib/**", "services/**", "packages/**"],
    "test_globs": ["tests/**", "test/**", "**/__tests__/**", "**/test_*.py", "**/*_test.*",
                   "**/*.test.*", "**/*.spec.*", "src/itest/**"],
    "protected_block": [],          # e.g. generated code, frozen packages
    "protected_ask": [".claude/settings.json", ".claude/hooks/**", ".sdlc/config.json",
                      ".sdlc/bin/**", ".github/workflows/**", "REVIEW.md"],
    "change_ticket_paths": ["migrations/**", "**/migrations/**", "infra/**", "terraform/**"],
    "plan_gate": "ask",             # off | ask | block : source edits need an approved plan
    "plan_sync_ignore": ["CLAUDE.md", "AGENTS.md", "lessons/**", "**/*.lock",
                         "package-lock.json", "pnpm-lock.yaml", "poetry.lock", "go.sum"],
    "verify_commands": ["make verify"],
    "verify_gate": True,            # no commit / stop with unverified source changes
    "format_commands": [],          # [{"glob": "**/*.py", "cmd": "ruff format {file} && ruff check {file}"}]
    "production_patterns": [r"deploy\b.*\bprod(uction)?\b", r"--env[= ]prod(uction)?\b",
                            r"kubectl\b.*--context[= ]\S*prod", r"terraform\s+apply\b.*prod",
                            r"helm\s+(upgrade|install)\b.*prod"],
    "protected_branches": ["main", "master", "release/*"],
}

SECRET_PATTERNS = [
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("private key block", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY-----"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    ("Anthropic API key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI-style API key", r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b"),
    ("Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("hard-coded credential",
     r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"]([^'\"\s]{12,})['\"]"),
]
PLACEHOLDER = re.compile(r"(?i)\$\{|<[^>]+>|example|placeholder|changeme|dummy|xxxx|redacted|your[_-]")
ALLOW_MARK = "sdlc:allow-secret"
ARTIFACTS = {"intent.md", "spec.md", "plan.md"}


# ---------------------------------------------------------------- helpers
def glob_re(glob: str) -> re.Pattern:
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


def expand_braces(glob: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", glob)
    if not m:
        return [glob]
    return [x for alt in m.group(1).split(",")
            for x in expand_braces(glob[:m.start()] + alt + glob[m.end():])]


def matches(rel: str, globs) -> bool:
    for g in (x for g0 in (globs or []) for x in expand_braces(g0)):
        target = rel if "/" in g else rel.rsplit("/", 1)[-1]  # slash-less glob = basename
        if glob_re(g).match(target):
            return True
    return False


def find_root(start: str | None) -> Path | None:
    p = Path(start or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        if (d / ".sdlc" / "config.json").is_file():
            return d
    return None


def load_config(root: Path) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(json.loads((root / ".sdlc" / "config.json").read_text()))
    return cfg


def rel_to(root: Path, path: str) -> str | None:
    try:
        p = Path(path)
        p = (p if p.is_absolute() else root / p).resolve()
        return p.relative_to(root).as_posix()
    except (ValueError, OSError):
        return None


def frontmatter(text: str) -> dict:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "\t", "#")):
                k, v = line.split(":", 1)
                v = re.split(r"\s+#", v, maxsplit=1)[0]  # drop inline YAML comments
                out[k.strip().lower()] = v.strip().strip("'\"")
    return out


def state_dir(root: Path) -> Path:
    d = root / ".sdlc" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_change(root: Path, cfg: dict) -> Path | None:
    cid = os.environ.get("SDLC_CHANGE", "").strip()
    f = root / ".sdlc" / "state" / "active-change"
    if not cid and f.is_file():
        cid = f.read_text().strip()
    if not cid:
        return None
    d = root / cfg["changes_dir"] / cid
    return d if d.is_dir() else None


def plan_info(change: Path | None, text: str | None = None):
    """Return (status, [file globs]) from plan.md (or the given text), or (None, None) if absent."""
    if text is None:
        if not change or not (change / "plan.md").is_file():
            return None, None
        text = (change / "plan.md").read_text(errors="replace")
    status = frontmatter(text).get("status", "").lower()
    m = re.search(r"^##\s*Files that change\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    files = []
    if m:
        section = m.group(1)
        files = re.findall(r"`([^`\s]+)`", section)
        if not files:
            files = [t.strip(",;") for t in re.split(r"[\s,]+", section)
                     if ("/" in t or "." in t) and not t.startswith(("-", "("))]
    return status, files


def scan_secrets(text: str) -> list[str]:
    hits = []
    for line in text.splitlines():
        if ALLOW_MARK in line:
            continue
        for name, pat in SECRET_PATTERNS:
            m = re.search(pat, line)
            if not m:
                continue
            if name == "hard-coded credential" and PLACEHOLDER.search(m.group(1)):
                continue
            hits.append(name)
    return sorted(set(hits))


def git(root: Path, *args) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    return r.stdout if r.returncode == 0 else ""


def deny(reason: str):
    print(f"[sdlc] BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)


def ask(reason: str):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "ask",
        "permissionDecisionReason": f"[sdlc] Human approval needed: {reason}"}}))
    sys.exit(0)


def fix_mode(root: Path) -> bool:
    # Prefer the env var: the human sets it when starting the session, the agent cannot.
    return os.environ.get("SDLC_FIX_MODE") == "1" or (root / ".sdlc" / "state" / "fix-mode").exists()


def newest_mtime(root: Path, rels) -> float:
    ts = [(root / r).stat().st_mtime for r in rels if (root / r).exists()]
    return max(ts) if ts else 0.0


def last_verify(root: Path) -> float:
    f = root / ".sdlc" / "state" / "last-verify"
    try:
        return float(f.read_text().strip())
    except (OSError, ValueError):
        return 0.0


def code_files(cfg, rels):
    return [r for r in rels if matches(r, cfg["source_globs"]) or matches(r, cfg["test_globs"])]


# ---------------------------------------------------------------- events
def pre_edit(root, cfg, data):
    ti = data.get("tool_input", {})
    rel = rel_to(root, ti.get("file_path") or ti.get("notebook_path") or "")
    if rel is None:
        return
    content = ti.get("content") or ti.get("new_string") or ti.get("new_source") or ""
    if ti.get("edits"):
        content = "\n".join(e.get("new_string", "") for e in ti["edits"])

    hits = scan_secrets(content)
    if hits:
        deny(f"{rel}: looks like a credential ({', '.join(hits)}). Load it from the environment or a "
             f"secret manager. If it is a known test value, add the comment '{ALLOW_MARK}' on that line.")
    if matches(rel, cfg["protected_block"]):
        deny(f"{rel} is a protected path (generated or frozen). See .sdlc/config.json protected_block "
             "and CLAUDE.md for where the change belongs instead.")
    if fix_mode(root) and matches(rel, cfg["test_globs"]) and (root / rel).exists():
        deny(f"fix mode is on: existing test {rel} is locked. Make the code pass the test; do not edit it. "
             "If the test itself is wrong, stop and tell the engineer.")

    asks = []
    if rel.rsplit("/", 1)[-1] in ARTIFACTS and re.search(
            r"(?im)^status:\s*(accepted|approved)\b", content):
        asks.append(f"{rel} is being marked accepted/approved. Only the named human approver may accept an "
                    "SDLC artifact; confirm you are that person and that 'approved_by' names you.")
    if matches(rel, cfg["change_ticket_paths"]) and not os.environ.get("CHANGE_TICKET"):
        asks.append(f"{rel} is a migration/infra path and needs a change ticket. Approve only if a ticket "
                    "exists (start sessions with CHANGE_TICKET=<id> to record it).")
    if matches(rel, cfg["protected_ask"]):
        asks.append(f"{rel} is agent/governance configuration; changes need owner review.")
    gate = cfg.get("plan_gate", "off")
    if gate != "off" and matches(rel, cfg["source_globs"]):
        change = active_change(root, cfg)
        status, _ = plan_info(change)
        if status != "approved":
            why = ("no active change (set .sdlc/state/active-change or SDLC_CHANGE)" if not change else
                   f"plan.md for {change.name} is '{status or 'missing'}', not approved")
            msg = f"editing source {rel} but {why}. Nothing is implemented without an accepted plan."
            if gate == "block":
                deny(msg)
            asks.append(msg)
    if asks:
        ask(" | ".join(asks))


def pre_bash(root, cfg, data):
    cmd = (data.get("tool_input") or {}).get("command", "")
    if any(re.search(p, cmd, re.I) for p in cfg["production_patterns"]) and not os.environ.get("RELEASE_APPROVAL"):
        deny("production actions need a named release authorization. The agent prepares the release; the "
             "release manager authorizes it (RELEASE_APPROVAL=<ticket> set by them, or run by the pipeline gate).")

    if re.search(r"\bgit\s+push\b", cmd):
        branches = cfg["protected_branches"]
        refs = [t.split(":")[-1] for t in shlex_split(cmd) if not t.startswith("-")]
        current = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
        explicit = [r for r in refs if r not in ("git", "push", "origin", "upstream")]
        targets = [current if r == "HEAD" else r for r in explicit] or [current]
        if any(matches(t, branches) for t in targets):
            deny(f"pushing to a protected branch ({', '.join(targets)}). Everything the agent writes "
                 "arrives as a PR through branch protection.")
        if re.search(r"--force\b|\s-f\b", cmd) and "--force-with-lease" not in cmd:
            ask("force push rewrites shared history.")

    if fix_mode(root):
        writes = re.search(r"(\bsed\s+-i|\bperl\s+-i|>|\btee\b|\bmv\b|\brm\b|\bgit\s+(checkout|restore)\b)", cmd)
        if writes:
            for tok in shlex_split(cmd):
                rel = rel_to(root, tok)
                if rel and matches(rel, cfg["test_globs"]) and (root / rel).exists():
                    deny(f"fix mode is on: {rel} is a locked test and this command could modify it.")

    if re.search(r"\bgit\s+commit\b", cmd):
        all_tracked = bool(re.search(r"\s-[a-zA-Z]*a|\s--all\b", cmd))
        commit_checks(root, cfg, include_unstaged=all_tracked, deny_fn=deny)


def shlex_split(cmd: str):
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


def commit_checks(root, cfg, include_unstaged, deny_fn):
    staged = [f for f in git(root, "diff", "--cached", "--name-only").splitlines() if f]
    diff = git(root, "diff", "--cached", "-U0")
    if include_unstaged:
        staged += [f for f in git(root, "diff", "--name-only").splitlines() if f]
        diff += git(root, "diff", "-U0")
    added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    hits = scan_secrets(added)
    if hits:
        deny_fn(f"staged changes contain what looks like a credential ({', '.join(hits)}). Remove it before committing.")

    change = active_change(root, cfg)
    if change:
        plan_rel = f"{cfg['changes_dir']}/{change.name}/plan.md"
        # Check against the plan as it will be committed: the staged (index) version if any.
        staged_plan = git(root, "show", f":{plan_rel}") if not include_unstaged else ""
        status, plan_files = plan_info(change, staged_plan or None)
        if plan_files is not None:
            drift = [f for f in staged if not f.startswith(cfg["changes_dir"] + "/")
                     and not matches(f, plan_files) and not matches(f, cfg["plan_sync_ignore"])]
            if drift:
                deny_fn("these files are not in plan.md 'Files that change': " + ", ".join(sorted(set(drift)))
                        + f". Implementation departed from the plan: add them to {plan_rel} (files, order, "
                          "risks, Deviations) and stage it in the same commit.")

    if cfg.get("verify_gate"):
        # behaviour-changing files only: a tests-only commit (e.g. a reproducing failing test) is allowed
        code = [f for f in staged if matches(f, cfg["source_globs"]) and not matches(f, cfg["test_globs"])]
        if code and newest_mtime(root, code) > last_verify(root):
            deny_fn(f"source changes are not verified since their last edit. Run "
                    f"{' / '.join(cfg['verify_commands'])}, read the output, fix failures, then commit.")


def post_edit(root, cfg, data):
    rel = rel_to(root, (data.get("tool_input") or {}).get("file_path", ""))
    if not rel or not (root / rel).exists():
        return
    for fc in cfg["format_commands"]:
        if matches(rel, [fc["glob"]]):
            cmd = fc["cmd"].replace("{file}", shlex.quote(rel))
            r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                print(f"[sdlc] format/lint failed for {rel}:\n{(r.stdout + r.stderr)[-3000:]}", file=sys.stderr)
                sys.exit(2)  # PostToolUse: feeds the failure back to Claude to fix now


def post_bash(root, cfg, data):
    cmd = (data.get("tool_input") or {}).get("command", "")
    resp = data.get("tool_response") or {}
    text = json.dumps(resp) if not isinstance(resp, str) else resp
    failed = (isinstance(resp, dict) and (resp.get("interrupted") or resp.get("is_error")
                                          or resp.get("exit_code") not in (None, 0))) \
        or bool(re.search(r"(?i)exit code:? *[1-9]|\bmake: \*\*\*", text))
    if not failed and any(v in cmd for v in cfg["verify_commands"]):
        (state_dir(root) / "last-verify").write_text(str(time.time()))


def stop(root, cfg, data):
    if not cfg.get("verify_gate") or data.get("stop_hook_active"):
        return
    changed = [l[3:].split(" -> ")[-1].strip('"') for l in git(root, "status", "--porcelain", "-uall").splitlines()]
    code = code_files(cfg, changed)
    if code and newest_mtime(root, code) > last_verify(root):
        print(json.dumps({"decision": "block", "reason":
              f"[sdlc] {len(code)} changed source/test file(s) not verified since last edit. Run "
              f"{' / '.join(cfg['verify_commands'])}, fix failures, and paste the output as evidence before "
              "reporting done. If this task is intentionally unfinished, say so explicitly."}))


def git_pre_commit(root, cfg):
    def fail(msg):
        print(f"[sdlc] commit blocked: {msg}", file=sys.stderr)
        sys.exit(1)
    cfg = dict(cfg, verify_gate=False)  # humans/other agents: CI enforces verification
    commit_checks(root, cfg, include_unstaged=False, deny_fn=fail)


def doctor(root, cfg):
    change = active_change(root, cfg)
    status, files = plan_info(change)
    print(json.dumps({"root": str(root), "active_change": change.name if change else None,
                      "plan_status": status, "plan_files": files, "fix_mode": fix_mode(root),
                      "last_verify": last_verify(root), "config": cfg}, indent=2))


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    data = {}
    if event not in ("git-pre-commit", "doctor"):
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    root = find_root(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR"))
    if root is None:
        return  # project has not adopted the SDLC kit: stay inert
    try:
        cfg = load_config(root)
    except (json.JSONDecodeError, OSError) as e:
        target = rel_to(root, (data.get("tool_input") or {}).get("file_path", "")) or ""
        if event.startswith("pre") and target != ".sdlc/config.json":
            deny(f".sdlc/config.json is invalid ({e}); fix it first.")
        return
    handlers = {"pre-edit": pre_edit, "pre-bash": pre_bash, "post-edit": post_edit,
                "post-bash": post_bash, "stop": stop}
    if event in handlers:
        handlers[event](root, cfg, data)
    elif event == "git-pre-commit":
        git_pre_commit(root, cfg)
    elif event == "doctor":
        doctor(root, cfg)
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # fail closed for gates, open for advisory events
        ev = sys.argv[1] if len(sys.argv) > 1 else ""
        print(f"[sdlc] hook error in {ev}: {e!r}", file=sys.stderr)
        sys.exit(2 if ev.startswith("pre") else 1)
