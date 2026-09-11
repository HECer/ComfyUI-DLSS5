---
name: ship
description: |
  Fully automated ship workflow. Merges the base branch, runs tests, audits coverage,
  reviews the diff, generates a CHANGELOG entry, bumps the version, commits, pushes,
  and creates the PR. Use when asked to "ship", "create a PR", or "open a pull request".
triggers:
  - ship
  - create a pr
  - open a pull request
  - ship this branch
---

# Ship: Fully Automated Ship Workflow

You are running the `ship` workflow. This is a **non-interactive, fully automated** workflow. Do NOT ask for confirmation at any step. The user said `/ship` which means DO IT. Run straight through and output the PR URL at the end.

**Only stop for:**
- On the base branch (abort)
- Merge conflicts that can't be auto-resolved (stop, show conflicts)
- In-branch test failures (pre-existing failures are triaged, not auto-blocking)
- Pre-landing review finds ASK items that need user judgment
- MINOR or MAJOR version bump needed (ask — see Step 12)
- AI-assessed coverage below minimum threshold (hard gate with user override — see Step 7)
- Plan items NOT DONE with no user override (see Step 8)

**Never stop for:**
- Uncommitted changes (always include them)
- Version bump choice (auto-pick MICRO or PATCH — see Step 12)
- CHANGELOG content (auto-generate from diff)
- Commit message approval (auto-commit)
- Multi-file changesets (auto-split into bisectable commits)
- TODOS.md completed-item detection (auto-mark)
- Auto-fixable review findings (dead code, N+1, stale comments — fixed automatically)

**Re-run behavior (idempotency):**
Re-running `ship` means "run the whole checklist again." Every verification step runs on every invocation. Only *actions* are idempotent:
- Step 12: If VERSION already bumped, skip the bump but still read the version
- Step 17: If already pushed, skip the push command
- Step 19: If PR exists, update the body instead of creating a new PR

---

## Step 0: Detect platform and base branch

Detect the git hosting platform from the remote URL:

```bash
git remote get-url origin 2>/dev/null
```

- URL contains "github.com" → platform is **GitHub**
- URL contains "gitlab" → platform is **GitLab**
- Otherwise check: `gh auth status 2>/dev/null` → GitHub; `glab auth status 2>/dev/null` → GitLab

Determine the base branch (target of the PR, or the repo's default):

- GitHub: `gh pr view --json baseRefName -q .baseRefName` or `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`
- GitLab: `glab mr view -F json 2>/dev/null` → extract `target_branch`
- Fallback: `git symbolic-ref refs/remotes/origin/HEAD`, then `main`, then `master`

Print the detected base branch. Use it as `<base>` in all subsequent commands.

---

## Step 1: Pre-flight

1. Check the current branch. If on the base branch or the repo's default branch, **abort**: "You're on the base branch. Ship from a feature branch."

2. Run `git status` (never use `-uall`). Uncommitted changes are always included — no need to ask.

3. Run `git diff <base>...HEAD --stat` and `git log <base>..HEAD --oneline` to understand what's being shipped.

4. **Review readiness check:** Check if a recent pre-landing review or plan review exists in this session (from the conversation context). If a plan-eng-review or review was run recently and found no blocking issues, note it. If no review has been run, note it — ship will run its own review in Step 9.

Check diff size: `git diff <base>...HEAD --stat | tail -1`. If the diff is >200 lines, add: "Note: This is a large diff. Consider running `plan-eng-review` for architecture-level review before shipping."

Continue to Step 2 — do NOT block or ask. Ship runs its own review in Step 9.

---

## Step 2: Distribution Pipeline Check

If the diff introduces a new standalone artifact (CLI binary, library package, tool) — not a web service with existing deployment — verify that a distribution pipeline exists.

1. Check if the diff adds a new `cmd/` directory, `main.go`, or `bin/` entry point.

2. If new artifact detected, check for a release workflow in `.github/workflows/` or `.gitlab-ci.yml`.

3. **If no release pipeline exists and a new artifact was added:** Use AskUserQuestion:
   - "This PR adds a new binary/tool but there's no CI/CD pipeline to build and publish it."
   - A) Add a release workflow now
   - B) Defer — add to TODOS.md
   - C) Not needed — this is internal/web-only

4. If release pipeline exists or no new artifact detected: Continue silently.

---

## Step 3: Merge the base branch (BEFORE tests)

Fetch and merge the base branch into the feature branch so tests run against the merged state:

```bash
git fetch origin <base> && git merge origin/<base> --no-edit
```

**If there are merge conflicts:** Try to auto-resolve if simple (VERSION, schema.rb, CHANGELOG ordering). If conflicts are complex or ambiguous, **STOP** and show them.

**If already up to date:** Continue silently.

---

## Step 4: Test Framework Bootstrap

**Detect existing test framework and project runtime:**

```bash
[ -f Gemfile ] && echo "RUNTIME:ruby"
[ -f package.json ] && echo "RUNTIME:node"
[ -f requirements.txt ] || [ -f pyproject.toml ] && echo "RUNTIME:python"
[ -f go.mod ] && echo "RUNTIME:go"
[ -f Cargo.toml ] && echo "RUNTIME:rust"
[ -f Gemfile ] && grep -q "rails" Gemfile 2>/dev/null && echo "FRAMEWORK:rails"
[ -f package.json ] && grep -q '"next"' package.json 2>/dev/null && echo "FRAMEWORK:nextjs"
ls jest.config.* vitest.config.* playwright.config.* .rspec pytest.ini pyproject.toml phpunit.xml 2>/dev/null
ls -d test/ tests/ spec/ __tests__/ cypress/ e2e/ 2>/dev/null
```

**If test framework detected:** Print "Test framework detected: {name}. Skipping bootstrap." Read 2-3 existing test files to learn conventions. **Skip the rest of bootstrap.**

**If NO runtime detected:** Use AskUserQuestion: "I couldn't detect your project's language. What runtime are you using?"
Options: A) Node.js/TypeScript B) Ruby/Rails C) Python D) Go E) Rust F) PHP G) Elixir H) This project doesn't need tests.

**If runtime detected but no test framework:** Research best practices for the detected runtime. Ask the user which test framework to set up. Install, configure, run first tests, set up CI if GitHub Actions is detected, write TESTING.md and update CLAUDE.md.

---

## Step 5: Run tests (on merged code)

Run the project's test suite. Consult CLAUDE.md for the test command. If no command is documented, use the detected test framework's default.

Run tests and capture output. If the project has multiple test suites (e.g. unit + frontend), run them in parallel.

**If any test fails:** Do NOT immediately stop. Apply Test Failure Ownership Triage:

### Test Failure Ownership Triage

#### Step T1: Classify each failure

For each failing test:

1. Get the files changed on this branch: `git diff origin/<base>...HEAD --name-only`
2. Classify:
   - **In-branch** if: the failing test file itself was modified on this branch, OR the test output references code that was changed on this branch.
   - **Likely pre-existing** if: neither the test file nor the code it tests was modified on this branch.
   - When ambiguous, default to **in-branch**.

#### Step T2: Handle in-branch failures

**STOP.** These are your failures. Show them. The developer must fix their own broken tests before shipping.

#### Step T3: Handle pre-existing failures

Use AskUserQuestion:

> These test failures appear pre-existing (not caused by your branch changes):
> [list each failure with file:line and brief error description]
>
> RECOMMENDATION: Choose A — fix now while the context is fresh.
> A) Investigate and fix now (recommended)
> B) Add as P0 TODO — fix after this branch lands
> C) Skip — I know about this, ship anyway

#### Step T4: Execute the chosen action

**If "Investigate and fix now":**
- Fix the pre-existing failure.
- Commit the fix separately: `git commit -m "fix: pre-existing test failure in <test-file>"`
- Continue with the workflow.

**If "Add as P0 TODO":**
- Add an entry to TODOS.md (or create it) with priority P0.
- Continue — treat the pre-existing failure as non-blocking.

**If "Skip":**
- Continue. Note: "Pre-existing test failure skipped: <test-name>"

**After triage:** If any in-branch failures remain unfixed, **STOP**. If all failures were pre-existing and handled, continue to Step 6.

**If all pass:** Continue silently — just note the counts briefly.

---

## Step 6: Eval Suites (conditional)

Evals are mandatory when prompt-related files change. Skip this step entirely if no prompt files are in the diff.

1. Check if the diff touches prompt-related files. Match against patterns listed in CLAUDE.md (look for `Prompt/LLM changes` or a `## Evals` section).

2. If no matches: Print "No prompt-related files changed — skipping evals." and continue to Step 9.

3. If matches: Identify affected eval suites and run them at full tier (if eval infrastructure exists). If any eval fails, show the failures and **STOP**. If all pass, note pass counts.

---

## Step 7: Test Coverage Audit

**Dispatch this step as a subagent** using the Agent tool with `subagent_type: "general-purpose"`. The subagent runs the coverage audit in a fresh context window — the parent only sees the conclusion.

**Subagent prompt:** Pass these instructions to the subagent, with `<base>` substituted:

> You are running a ship-workflow test coverage audit. Run `git diff <base>...HEAD` as needed. Do not commit or push — report only.
>
> 100% coverage is the goal — every untested path is a path where bugs hide.
>
> **Test Framework Detection:** Read CLAUDE.md for a `## Testing` section. If not found, auto-detect by checking for jest.config.*, vitest.config.*, .rspec, pytest.ini, go.mod, Cargo.toml, etc.
>
> **0. Count test files before any generation:**
> `find . -name '*.test.*' -o -name '*.spec.*' -o -name '*_test.*' -o -name '*_spec.*' | grep -v node_modules | wc -l`
>
> **1. Trace every codepath changed** using `git diff <base>...HEAD`. For each changed file, trace how data flows through the code. Draw ASCII diagrams showing every function/method, every conditional branch, every error path.
>
> **2. Map user flows, interactions, and error states.** For each changed feature, think through user flows, interaction edge cases, error states the user can see, and empty/zero/boundary states.
>
> **3. Check each branch against existing tests.** Go branch by branch. Rate each: ★★★ (behavior + edge + error), ★★ (happy path), ★ (smoke test).
>
> **4. Output ASCII coverage diagram** with both code paths and user flows. Mark [→E2E] for integration-test-worthy paths and [→EVAL] for LLM eval-worthy paths. Include COVERAGE: N/M (X%) line.
>
> **5. Generate tests for uncovered paths.** Read 2-3 existing test files to match conventions. Write real tests with meaningful assertions. Run each test. Passes → keep. Fails → fix once. Still fails → delete silently. Cap: 20 tests maximum.
>
> **6. Count test files after generation.** For PR body: "Tests: {before} → {after} (+{delta} new)"
>
> **Coverage gate:** Check CLAUDE.md for `## Test Coverage` section with `Minimum:` and `Target:` fields. Default: Minimum=60%, Target=80%. If below target, report it.
>
> After your analysis, output a single JSON object on the LAST LINE of your response:
> `{"coverage_pct":N,"gaps":N,"diagram":"<full markdown coverage diagram>","tests_added":["path",...]}`

**Parent processing:**
1. Parse the LAST line as JSON.
2. Store `coverage_pct` for Step 20 metrics.
3. Embed `diagram` verbatim in the PR body's `## Test Coverage` section (Step 19).
4. Print: `Coverage: {coverage_pct}%, {gaps} gaps. {tests_added.length} tests added.`

**Coverage gate:** If coverage_pct < minimum (60%), use AskUserQuestion to ask whether to generate more tests or override. If coverage_pct >= target (80%), pass silently.

**If the subagent fails or returns invalid JSON:** Fall back to running the audit inline. Never block ship on subagent failure.

---

## Step 8: Plan Completion Audit

**Dispatch this step as a subagent** using the Agent tool with `subagent_type: "general-purpose"`. The subagent reads the plan file in its own fresh context.

**Subagent prompt:** Pass these instructions:

> You are running a ship-workflow plan completion audit. The base branch is `<base>`. Use `git diff <base>...HEAD` to see what shipped. Do not commit or push — report only.
>
> **Plan File Discovery:**
> 1. Check if there is an active plan file in the conversation context (plan file paths may be referenced in system messages).
> 2. If not found, search by content:
> ```bash
> BRANCH=$(git branch --show-current 2>/dev/null | tr '/' '-')
> REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
> for PLAN_DIR in "$HOME/.claude/plans" ".claude/plans" "."; do
>   [ -d "$PLAN_DIR" ] || continue
>   PLAN=$(ls -t "$PLAN_DIR"/*.md 2>/dev/null | xargs grep -l "$BRANCH" 2>/dev/null | head -1)
>   [ -z "$PLAN" ] && PLAN=$(find "$PLAN_DIR" -name '*.md' -mmin -1440 -maxdepth 1 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
>   [ -n "$PLAN" ] && break
> done
> [ -n "$PLAN" ] && echo "PLAN_FILE: $PLAN" || echo "NO_PLAN_FILE"
> ```
> 3. If a plan file was found via content-based search, read the first 20 lines and verify it is relevant to the current branch's work.
>
> No plan file found → skip with "No plan file detected — skipping."
>
> **Actionable Item Extraction:** Read the plan. Extract checkboxes, numbered steps, imperative statements, file-level specs, test requirements, data model changes. Ignore context/background sections, questions/TBD items, explicitly deferred items. Cap at 50 items.
>
> **Cross-Reference Against Diff:** For each item: DONE (clear evidence), PARTIAL (incomplete), NOT DONE (no evidence), CHANGED (different approach, same goal).
>
> **Output:**
> ```
> PLAN COMPLETION AUDIT
> ═══════════════════════
> Plan: {path}
>   [DONE]     Create UserService
>   [NOT DONE] Add caching layer
> COMPLETION: N/M DONE
> ```
>
> **Gate Logic:** If any NOT DONE items exist, ask: Stop to implement / Ship anyway + defer to P1 TODOs / Intentionally dropped.
>
> After your analysis, output a single JSON object on the LAST LINE:
> `{"total_items":N,"done":N,"changed":N,"deferred":N,"summary":"<markdown checklist for PR body>"}`

**Parent processing:** Parse the LAST line as JSON. If `deferred > 0` and no user override, present deferred items via AskUserQuestion before continuing. Embed `summary` in PR body.

**If the subagent fails or returns invalid JSON:** Fall back to running the audit inline.

---

## Step 8.1: Plan Verification

Using the plan file already discovered in Step 8, look for a verification section. Match headings: `## Verification`, `## Test plan`, `## Testing`, `## How to test`, or similar.

**If no verification section found:** Skip with "No verification steps found in plan — skipping auto-verification."

**If no plan file was found in Step 8:** Skip.

Check if a dev server is reachable before invoking browser-based verification:

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 2>/dev/null || \
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080 2>/dev/null || \
curl -s -o /dev/null -w '%{http_code}' http://localhost:5173 2>/dev/null || echo "NO_SERVER"
```

**If NO_SERVER:** Skip with "No dev server detected — skipping plan verification."

If a dev server is reachable and a verification section exists: Execute the verification steps using the browser MCP (Playwright) or by running the project's automated test suite. Treat each verification item as a test case.

- **All pass:** Continue silently. "Plan verification: PASS."
- **Any FAIL:** Use AskUserQuestion showing failures. Options: A) Fix before shipping, B) Ship anyway — known issues.

---

## Step 8.2: Scope Drift Detection

Before reviewing code quality, check: **did they build what was requested — nothing more, nothing less?**

1. Read `TODOS.md` (if it exists). Read PR description. Read commit messages.
2. Identify the **stated intent** — what was this branch supposed to accomplish?
3. Run `git diff origin/<base>...HEAD --stat` and compare files changed against stated intent.

4. Evaluate for:
   - **SCOPE CREEP** — files changed that are unrelated to the stated intent
   - **MISSING REQUIREMENTS** — requirements not addressed in the diff

5. Output:
   ```
   Scope Check: [CLEAN / DRIFT DETECTED / REQUIREMENTS MISSING]
   Intent: <1-line summary of what was requested>
   Delivered: <1-line summary of what the diff actually does>
   ```

6. This is **INFORMATIONAL** — does not block the review. Proceed.

---

## Step 9: Pre-Landing Review

Review the diff for structural issues that tests don't catch.

1. Read `.claude/skills/review/checklist.md`. If the file cannot be read, continue with the built-in checks below.

2. Run `git diff origin/<base>` to get the full diff.

3. Apply the review checklist in two passes:
   - **Pass 1 (CRITICAL):** SQL & Data Safety, LLM Output Trust Boundary violations, Shell Injection, Race Conditions, Enum Completeness
   - **Pass 2 (INFORMATIONAL):** All remaining categories (async/sync mixing, N+1, stale comments, dead code)

**Confidence Calibration:** Every finding must include a confidence score (1-10).
- 9-10: Verified by reading specific code. Show normally.
- 7-8: High confidence. Show normally.
- 5-6: Moderate. Show with caveat "Medium confidence, verify this is actually an issue."
- 3-4: Low. Suppress from main report — include in appendix only.
- 1-2: Speculation. Only report if P0.

**Finding format:** `[SEVERITY] (confidence: N/10) file:line — description`

### Design Review (conditional)

Check if the diff touches frontend files:

```bash
git diff origin/<base> --name-only | grep -iE '\.(tsx?|jsx?|css|scss|sass|vue|svelte|html)$' | head -5
```

If frontend files changed:
1. Read `DESIGN.md` or `design-system.md` in the repo root (if it exists). Findings are calibrated against it.
2. Read `.claude/skills/review/design-checklist.md` (if it exists). If not found, use universal design principles.
3. Apply the design checklist against changed frontend files.
4. Mechanical CSS AUTO-FIX items: apply directly. Design judgment ASK items: present to user.

### Step 9.1: Adversarial Review (always-on)

Dispatch an independent subagent via the Agent tool. The subagent has fresh context — no checklist bias from the structured review.

Subagent prompt:
"Read the diff for this branch with `git diff origin/<base>`. Think like an attacker and a chaos engineer. Your job is to find ways this code will fail in production. Look for: edge cases, race conditions, security holes, resource leaks, failure modes, silent data corruption, logic errors that produce wrong results silently, error handling that swallows failures, and trust boundary violations. Be adversarial. Be thorough. No compliments — just the problems. For each finding, classify as FIXABLE (you know how to fix it) or INVESTIGATE (needs human judgment)."

Present findings under an `ADVERSARIAL REVIEW (subagent):` header. **FIXABLE findings** flow into the same Fix-First pipeline as the structured review. **INVESTIGATE findings** are presented as informational.

**Cross-review synthesis:**
```
ADVERSARIAL REVIEW SYNTHESIS:
  High confidence (found by multiple sources): [findings agreed on by >1 pass]
  Unique to structured review: [from checklist pass]
  Unique to adversarial subagent: [from subagent]
```

### Step 9.2: Fix-First Flow

After all review passes (checklist + adversarial):

1. **Classify each finding as AUTO-FIX or ASK:**
   - AUTO-FIX: mechanical, low-risk, single-file changes (dead code, stale comments, obvious formatting)
   - ASK: architectural, security-sensitive, ambiguous scope, or user preference

2. **Auto-fix all AUTO-FIX items.** Apply each fix. Output: `[AUTO-FIXED] [file:line] Problem → what you did`

3. **If ASK items remain,** present them in ONE AskUserQuestion:
   - List each with number, severity, problem, recommended fix
   - Per-item options: A) Fix  B) Skip
   - Overall RECOMMENDATION

4. **After all fixes (auto + user-approved):**
   - If ANY fixes were applied: commit fixed files by name (`git add <fixed-files> && git commit -m "fix: pre-landing review fixes"`), then **STOP** and tell the user to run `ship` again to re-test.
   - If no fixes applied: continue to Step 12.

5. Output summary: `Pre-Landing Review: N issues — M auto-fixed, K asked (J fixed, L skipped)`

---

## Step 10: Address Code Review Comments (if PR exists)

If a PR already exists, check for any open review comments:

- **GitHub:** `gh pr review list` and `gh api repos/:owner/:repo/pulls/{pr_number}/comments`
- **GitLab:** `glab mr view --comments`

For each comment:
- **VALID & ACTIONABLE:** Use AskUserQuestion. Options: A) Fix now, B) Acknowledge and ship anyway, C) It's a false positive.
- **ALREADY FIXED in this diff:** Reply to the comment noting it was fixed.

If fixes were applied, re-run tests (Step 5) before continuing.

If no PR exists yet: skip this step silently.

---

## Step 11: (Placeholder for future steps)

Continue to Step 12.

---

## Step 12: Version bump (auto-decide)

**Idempotency check:** Compare `VERSION` against the base branch.

```bash
BASE_VERSION=$(git show origin/<base>:VERSION 2>/dev/null | tr -d '\r\n[:space:]' || echo "0.0.0.0")
CURRENT_VERSION=$(cat VERSION 2>/dev/null | tr -d '\r\n[:space:]' || echo "0.0.0.0")
echo "BASE: $BASE_VERSION  VERSION: $CURRENT_VERSION"
```

If `CURRENT_VERSION == BASE_VERSION`: **STATE = FRESH** → proceed with bump.
If `CURRENT_VERSION != BASE_VERSION`: **STATE = ALREADY_BUMPED** → skip bump, reuse `CURRENT_VERSION`.

**If FRESH — auto-decide the bump level:**
- Count lines changed: `git diff origin/<base>...HEAD --stat | tail -1`
- Check for feature signals: new route/page files, new DB migrations, branch name starting with `feat/`
- **MICRO** (4th digit): < 50 lines changed, trivial tweaks, typos, config
- **PATCH** (3rd digit): 50+ lines changed, no feature signals detected
- **MINOR** (2nd digit): **ASK the user** if ANY feature signal is detected, OR 500+ lines changed, OR new packages added
- **MAJOR** (1st digit): **ASK the user** — only for milestones or breaking changes

Compute new version (bumping a digit resets all digits to its right to 0). Write it to `VERSION` (and `package.json` if it exists).

---

## Step 13: CHANGELOG (auto-generate)

1. Read `CHANGELOG.md` header to know the format.

2. **Enumerate every commit on the branch:**
   ```bash
   git log <base>..HEAD --oneline
   ```

3. **Read the full diff** to understand what each commit actually changed.

4. **Group commits by theme:** New features, Performance, Bug fixes, Cleanup, Infrastructure, Refactoring.

5. **Write the CHANGELOG entry** covering ALL groups:
   - Categorize into `### Added`, `### Changed`, `### Fixed`, `### Removed`
   - Insert after the file header, dated today
   - Format: `## [X.Y.Z.W] - YYYY-MM-DD`
   - **Voice:** Lead with what the user can now **do**. Use plain language, not implementation details.

6. **Cross-check:** Every commit must map to at least one bullet point.

---

## Step 14: TODOS.md (auto-update)

1. Check if TODOS.md exists. If not, use AskUserQuestion: create it now or skip.

2. Check structure and organization (priority fields, component groupings, Completed section).

3. **Detect completed TODOs:** Using the diff and commit history already gathered, match TODO items against what was shipped. Be conservative — only mark items as completed when the diff clearly shows the work is done.

4. **Move completed items** to the `## Completed` section. Append: `**Completed:** vX.Y.Z (YYYY-MM-DD)`

5. Output summary: `TODOS.md: N items marked complete. M items remaining.`

---

## Step 15: Commit (bisectable chunks)

### Step 15.1: Bisectable Commits

Analyze the diff and group changes into logical commits. Each commit should represent **one coherent change** — not one file, but one logical unit.

**Commit ordering** (earlier commits first):
- Infrastructure: migrations, config changes, route additions
- Models & services: new models, services (with their tests)
- Controllers & views: controllers, views, components (with their tests)
- VERSION + CHANGELOG + TODOS.md: always in the final commit

**Rules for splitting:**
- A model and its test file go in the same commit
- A service and its test file go in the same commit
- If total diff is small (< 50 lines across < 4 files), a single commit is fine

**Each commit must be independently valid** — no broken imports, no references to code that doesn't exist yet.

The **final commit** contains VERSION + CHANGELOG. The project's commit identity and co-author policy always wins; never add an AI co-author trailer unless the project explicitly allows it.

```bash
git commit -m "chore: bump version and changelog (vX.Y.Z.W)"
```

---

## Step 16: Verification Gate

**IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before pushing, re-verify if code changed during Steps 4-13:

1. **Test verification:** If ANY code changed after Step 5's test run, re-run the test suite. Stale output from Step 5 is NOT acceptable.

2. **Build verification:** If the project has a build step, run it.

3. **Rationalization prevention:**
   - "Should work now" → RUN IT.
   - "I'm confident" → Confidence is not evidence.
   - "I already tested earlier" → Code changed since then. Test again.

**If tests fail here:** STOP. Do not push. Fix and return to Step 5.

---

## Step 17: Push

**Idempotency check:**

```bash
git fetch origin <branch-name> 2>/dev/null
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/<branch-name> 2>/dev/null || echo "none")
[ "$LOCAL" = "$REMOTE" ] && echo "ALREADY_PUSHED" || echo "PUSH_NEEDED"
```

If `ALREADY_PUSHED`, skip the push but continue to Step 18. Otherwise:

```bash
git push -u origin <branch-name>
```

**You are NOT done.** Continue to Step 18.

---

## Step 18: Documentation sync (via subagent, before PR creation)

**Dispatch the `document-release` workflow as a subagent** using the Agent tool with `subagent_type: "general-purpose"`.

**Subagent prompt:**

> You are executing the document-release workflow after a code push. Run the complete document-release workflow end-to-end. The skill's steps are: pre-flight & diff analysis, per-file doc audit, auto-updates, ask about risky changes, CHANGELOG voice polish, cross-doc consistency, TODOS cleanup, VERSION bump question, commit & output. Branch: `<branch>`, base: `<base>`.
>
> Do NOT attempt to edit the PR body — no PR exists yet.
>
> After completing the workflow, output a single JSON object on the LAST LINE of your response:
> `{"files_updated":["README.md","CLAUDE.md",...],"commit_sha":"abc1234","pushed":true,"documentation_section":"<markdown block for PR body ## Documentation section>"}`
>
> If no documentation files needed updating, output:
> `{"files_updated":[],"commit_sha":null,"pushed":false,"documentation_section":null}`

**Parent processing:**
1. Parse the LAST line as JSON.
2. Store `documentation_section` — Step 19 embeds it in the PR body.
3. Print: `Documentation synced: {N} files updated.` or `Documentation is current — no updates needed.`

**If the subagent fails or returns invalid JSON:** Warn and proceed to Step 19 without a `## Documentation` section.

---

## Step 19: Create PR/MR

**Idempotency check:** Check if a PR/MR already exists for this branch.

- GitHub: `gh pr view --json url,number,state 2>/dev/null`
- GitLab: `glab mr view -F json 2>/dev/null`

If an **open** PR/MR already exists: **update** the PR body with fresh results from this run. Never reuse stale PR body content. Print the existing URL and continue.

If no PR/MR exists: create one.

**PR/MR body:**

```markdown
## Summary
[Summarize ALL changes being shipped. Run `git log <base>..HEAD --oneline` to enumerate every commit. Group into logical sections. Every substantive commit must appear in at least one section.]

## Test Coverage
[coverage diagram from Step 7, or "All new code paths have test coverage."]
[If Step 7 ran: "Tests: {before} → {after} (+{delta} new)"]

## Pre-Landing Review
[findings from Step 9, or "No issues found."]

## Plan Completion
[If plan file found: completion checklist summary from Step 8]
[If no plan file: "No plan file detected."]

## Verification Results
[If verification ran: summary from Step 8.1]
[If skipped: reason]

## TODOS
[If items marked complete: bullet list with version]
[If no items completed: "No TODO items completed in this PR."]

## Documentation
[Embed documentation_section from Step 18 verbatim, or omit section if null]

## Test plan
- [x] All tests pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

**GitHub:**
```bash
gh pr create --base <base> --title "<type>: <summary>" --body "..."
```

**GitLab:**
```bash
glab mr create -b <base> -t "<type>: <summary>" -d "..."
```

**If neither CLI is available:** Print the branch name, remote URL, and instruct the user to create the PR/MR manually.

**Output the PR/MR URL** — then proceed to Step 20.

---

## Step 20: Record metrics (in project state)

Save ship metrics to the project's `.context/` directory for `retro` to track trends:

```bash
mkdir -p .context/ships
```

Use the Write tool to append a JSON line to `.context/ships/log.jsonl`:

```json
{"skill":"ship","timestamp":"<ISO datetime>","coverage_pct":N,"plan_items_total":N,"plan_items_done":N,"version":"X.Y.Z.W","branch":"<branch>","pr_url":"<url>"}
```

This step is automatic — never skip it, never ask for confirmation.

---

## Important Rules

- **Never skip tests.** If tests fail, stop.
- **Never force push.** Use regular `git push` only.
- **Never ask for trivial confirmations** (e.g., "ready to push?", "create PR?"). DO stop for: version bumps (MINOR/MAJOR), pre-landing review ASK items.
- **Always use the 4-digit version format** from the VERSION file (MAJOR.MINOR.PATCH.MICRO).
- **Date format in CHANGELOG:** `YYYY-MM-DD`
- **Split commits for bisectability** — each commit = one logical change.
- **TODOS.md completion detection must be conservative.** Only mark items as completed when the diff clearly shows the work is done.
- **Never push without fresh verification evidence.** If code changed after Step 5 tests, re-run before pushing.
- **The goal is: user says `ship`, next thing they see is the review + PR URL + auto-synced docs.**
