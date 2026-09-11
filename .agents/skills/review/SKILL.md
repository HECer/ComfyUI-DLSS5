---
name: review
description: |
  Pre-merge code review — the single canonical review of a change before it lands. Covers BOTH
  diff safety/structure (SQL safety, LLM trust-boundary violations, conditional side effects)
  AND engineering quality (architecture fit, edge cases, test coverage, performance). Use when
  asked to "review this PR", "code review", "pre-landing review", "check my diff", or before
  merging. (For plan-time review use plan-eng-review or plan-ceo-review instead.)
triggers:
  - review this pr
  - code review
  - check my diff
  - pre-landing review
---

# Pre-Landing PR Review

You are running the `review` workflow. Analyze the current branch's diff against the base branch for structural issues that tests don't catch.

---

## Step 0: Detect platform and base branch

Detect the git hosting platform from the remote URL:

```bash
git remote get-url origin 2>/dev/null
```

- URL contains "github.com" → platform is **GitHub**
- URL contains "gitlab" → platform is **GitLab**
- Otherwise check: `gh auth status 2>/dev/null` → GitHub; `glab auth status 2>/dev/null` → GitLab; neither → unknown

Determine the base branch (target of the PR, or the repo's default):

- GitHub: `gh pr view --json baseRefName -q .baseRefName` or `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`
- GitLab: `glab mr view -F json 2>/dev/null` → extract `target_branch` or `default_branch`
- Fallback: `git symbolic-ref refs/remotes/origin/HEAD`, then `origin/main`, then `origin/master`, then `main`

Print the detected base branch. Use it as `<base>` in all subsequent commands.

---

## Step 1: Check branch

1. Run `git branch --show-current`.
2. If on the base branch: output **"Nothing to review — you're on the base branch or have no changes against it."** and stop.
3. Run `git fetch origin <base> --quiet && git diff origin/<base> --stat`. If no diff, output the same message and stop.

---

## Step 1.5: Scope Drift Detection

Check whether the diff matches what was requested.

1. Read `TODOS.md` (if it exists). Read PR description (`gh pr view --json body --jq .body 2>/dev/null || true`). Read commit messages (`git log origin/<base>..HEAD --oneline`).
2. Identify the **stated intent** — what was this branch supposed to accomplish?
3. Run `git diff origin/<base>...HEAD --stat` and compare against the stated intent.

Evaluate for:
- **SCOPE CREEP** — files changed that are unrelated to stated intent; "while I was in there" changes
- **MISSING REQUIREMENTS** — requirements from TODOS.md/PR description not in the diff; partial implementations

Output (before the main review begins):
```
Scope Check: [CLEAN / DRIFT DETECTED / REQUIREMENTS MISSING]
Intent: <1-line summary of what was requested>
Delivered: <1-line summary of what the diff actually does>
[If drift: list each out-of-scope change]
[If missing: list each unaddressed requirement]
```

This is **INFORMATIONAL** — does not block the review.

---

## Step 1.6: Plan Completion Audit (optional)

Check if there is a plan file referenced in the conversation context or a recent `.md` file in common plan locations (e.g., `~/.claude/plans/`, `.claude/plans/`). If found and relevant to the current branch:

Extract actionable items (checkboxes, numbered steps, imperative statements, file-level specs, test requirements). Cross-reference each item against the diff:
- **DONE** — clear evidence in diff
- **PARTIAL** — some work started but incomplete
- **NOT DONE** — no evidence in diff
- **CHANGED** — goal met by different means

For `PARTIAL` or `NOT DONE`, investigate why and rate impact (HIGH/MEDIUM/LOW). For HIGH-impact gaps, use AskUserQuestion:
- A) Stop and implement missing items
- B) Ship anyway + create P1 TODOs
- C) Intentionally dropped

Output format:
```
PLAN COMPLETION AUDIT
═══════════════════════
Plan: {path}
  [DONE]     Create UserService — src/services/user_service.rb
  [NOT DONE] Add caching layer — no cache-related changes in diff
COMPLETION: N/M DONE
```

---

## Step 2: Read the checklist

Read `.claude/skills/review/checklist.md` (if it exists). If the file cannot be read, continue with the built-in checks below.

---

## Step 3: Get the diff

```bash
git fetch origin <base> --quiet
git diff origin/<base>
```

---

## Step 4: Critical review pass

Apply these categories against the diff:

**CRITICAL:**
- **SQL & Data Safety** — string interpolation in queries, missing parameterization, N+1 patterns
- **Race Conditions & Concurrency** — shared mutable state, missing locks, idempotency violations
- **LLM Output Trust Boundary** — LLM output used in SQL, shell commands, or DB writes without validation
- **Shell Injection** — user input passed to shell commands unsanitized
- **Enum & Value Completeness** — new enum values/types not handled in all switch/case branches

For Enum & Value Completeness: use Grep to find all files referencing sibling values, then Read those files. This requires looking outside the diff.

**INFORMATIONAL:**
- Async/sync mixing, column/field name safety, LLM prompt issues, type coercion, frontend/view issues, time window safety, completeness gaps, distribution/CI gaps

**Finding format:**
```
[SEVERITY] (confidence: N/10) file:line — description
```

Confidence scale:
- 9-10: Verified by reading specific code, concrete bug demonstrated
- 7-8: High confidence pattern match
- 5-6: Moderate — show with caveat "Medium confidence, verify this is actually an issue"
- 3-4: Low — include in appendix only
- 1-2: Speculation — only report if P0

---

## Step 4.5: Adversarial review (always-on)

Dispatch an independent subagent via the Agent tool to review the diff with fresh context. Subagent prompt:

> "Run `git diff origin/<base>` to get the diff. Think like an attacker and a chaos engineer. Find ways this code will fail in production: edge cases, race conditions, security holes, resource leaks, failure modes, silent data corruption, logic errors, error handling that swallows failures, trust boundary violations. For each finding, classify as FIXABLE (you know how to fix it) or INVESTIGATE (needs human judgment)."

Present findings under `ADVERSARIAL REVIEW (subagent):`. FIXABLE findings flow into the Fix-First pipeline. INVESTIGATE findings are informational.

---

## Step 5: Fix-First Review

### 5a: Classify each finding

For each finding from Steps 4 and 4.5:
- **AUTO-FIX** — mechanical, low-risk, single-file changes (dead code, stale comments, obvious formatting)
- **ASK** — architectural, security-sensitive, ambiguous scope, or user preference

### 5b: Apply AUTO-FIX items

Apply each fix directly. For each:
`[AUTO-FIXED] [file:line] Problem → what you did`

### 5c: Batch-ask about ASK items

Present all ASK items in one AskUserQuestion:
```
I auto-fixed N issues. M need your input:

1. [CRITICAL] file:line — description
   Fix: recommended fix
   → A) Fix  B) Skip

RECOMMENDATION: Fix all — [reason].
```

### 5d: Apply approved fixes

Apply fixes for items where the user chose "Fix."

---

## Step 5.5: TODOS cross-reference

Read `TODOS.md` (if it exists). Cross-reference the PR:
- Does this PR close any open TODOs? Note: "This PR addresses TODO: <title>"
- Does this PR create work that should become a TODO? Flag as informational.

---

## Step 5.6: Documentation staleness check

For each `.md` file in the repo root: if the code it describes was changed but the doc was NOT updated in this branch, flag as informational:
"Documentation may be stale: [file] describes [feature] but code changed. Consider running the `document-release` skill."

---

## Completion Status

Report one of:
- **DONE** — All steps completed, no blocking issues.
- **DONE_WITH_CONCERNS** — Completed with issues the user should know about.
- **BLOCKED** — Cannot proceed. State what is blocking.
- **NEEDS_CONTEXT** — Missing information required to continue.

## Important Rules

- **Read the FULL diff before commenting.** Do not flag issues already addressed in the diff.
- **Fix-first, not read-only.** AUTO-FIX items are applied directly; ASK items only after user approval.
- **Never commit, push, or create PRs** — that is the `ship` skill's job.
- **Be terse.** One line problem, one line fix. No preamble.
- **Only flag real problems.** Skip anything that is fine.

## Engineering-manager checklist

Beyond the structural/safety scan above, also review the change as an engineering manager would —
this is the angle the old `eng-review` skill covered, now folded in here so there is one
pre-merge review:

- **Architecture fit & data flow:** does the change follow the project's established patterns and
  data flow, or does it drift? Flag architectural drift.
- **Edge cases & error paths:** are unhandled inputs, failure modes, and boundary conditions
  covered?
- **Test coverage:** is the changed behavior covered by tests that verify behavior (not just
  mocks)? Missing or weak tests for changed behavior is a blocking issue.
- **Performance:** any obvious regressions (N+1, unbounded growth, needless work in hot paths)?

Output a pass/block verdict with specific, actionable findings. A reviewer never reviews their
own implementation (see `policy/roles.md`).

## Interactive cross-model review

Outside the loop, run `yoke review` to have a *second* model review your current diff
before you commit or push. It resolves to the first available of codex → gemini → claude
(preferring a model other than the one you are driving), reviews the uncommitted working
tree by default (or `--base=<ref>` for a branch range), and exits non-zero if it finds a
blocking issue — so it chains as a gate (`... && yoke review`) or a pre-push hook.
This is the interactive counterpart to the loop's `--review`/`--reviewer`.
