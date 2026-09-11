---
name: health
description: |
  Code Quality Dashboard. Runs the project's type-checker, linter, test runner, and
  dead-code detector, scores each category 0-10, and presents a dashboard with trends.
  Use when asked for a "health check", "code quality report", or "quality dashboard".
triggers:
  - health check
  - code quality
  - quality dashboard
---

# Code Quality Dashboard

You are running the `health` skill. Detect and run the project's quality tools, score each category, and present a dashboard.

---

## Step 1: Detect the health stack

Read `CLAUDE.md` and look for a `## Health Stack` section that lists the project's tools. If found, use those tools. If not found, auto-detect:

```bash
# Runtime detection
[ -f Gemfile ] && echo "RUNTIME:ruby"
[ -f package.json ] && echo "RUNTIME:node"
[ -f requirements.txt ] || [ -f pyproject.toml ] && echo "RUNTIME:python"
[ -f go.mod ] && echo "RUNTIME:go"
[ -f Cargo.toml ] && echo "RUNTIME:rust"

# Type checker
[ -f tsconfig.json ] && echo "TYPECHECK:tsc"
[ -f pyproject.toml ] && command -v mypy >/dev/null 2>&1 && echo "TYPECHECK:mypy"
[ -f Gemfile ] && grep -q "sorbet" Gemfile 2>/dev/null && echo "TYPECHECK:sorbet"

# Linter
[ -f .eslintrc* ] || [ -f eslint.config* ] && echo "LINT:eslint"
[ -f .rubocop.yml ] && echo "LINT:rubocop"
[ -f pyproject.toml ] && grep -qE "ruff|flake8" pyproject.toml 2>/dev/null && echo "LINT:ruff"
[ -f go.mod ] && echo "LINT:staticcheck"
[ -f Cargo.toml ] && echo "LINT:clippy"

# Test runner
[ -f jest.config* ] || [ -f vitest.config* ] && echo "TESTS:npm run test"
[ -f .rspec ] && echo "TESTS:bundle exec rspec"
[ -f pytest.ini ] || [ -f conftest.py ] && echo "TESTS:pytest"
[ -f go.mod ] && echo "TESTS:go test ./..."
[ -f Cargo.toml ] && echo "TESTS:cargo test"

# Dead code detector
command -v ts-prune >/dev/null 2>&1 && echo "DEADCODE:ts-prune"
command -v knip >/dev/null 2>&1 && echo "DEADCODE:knip"
[ -f go.mod ] && echo "DEADCODE:deadcode (go-deadcode)"
[ -f Cargo.toml ] && echo "DEADCODE:cargo udeps"
```

Print the detected stack. If nothing is detected, ask the user what tools to run.

---

## Step 2: Run the tools

Run each detected tool and capture output. Run them in parallel where possible.

**Type checker** (run the project's own type-checker, e.g. `tsc --noEmit`, `mypy .`, `srb tc`):
```bash
# Example for TypeScript:
npx tsc --noEmit 2>&1 | tail -20
```

**Linter** (run the project's own linter, e.g. `eslint`, `rubocop`, `ruff`):
```bash
# Example for ESLint:
npx eslint . --max-warnings 0 2>&1 | tail -30
```

**Test runner** (run the project's own test suite):
```bash
# Example for npm:
npm test -- --passWithNoTests 2>&1 | tail -40
```

**Dead-code detector** (run the project's own dead-code tool, e.g. `knip`, `ts-prune`):
```bash
# Example:
npx knip 2>&1 | tail -20
```

Capture raw counts: errors, warnings, test pass/fail/skip counts, dead-code count.

---

## Step 3: Score each category (0–10)

Score rules (apply for each category):

| Score | Meaning |
|-------|---------|
| 10 | Zero issues |
| 8-9 | 1-5 minor warnings, no errors |
| 6-7 | <20 warnings, zero errors |
| 4-5 | 20-50 warnings, or 1-5 errors |
| 2-3 | 50-100 warnings, or 6-20 errors |
| 0-1 | 100+ warnings, or 20+ errors, or tool fails to run |

For tests, also consider pass rate:
- 10 = 100% pass
- 8 = 95-99%
- 6 = 80-94%
- 4 = 50-79%
- 0-2 = <50%

---

## Step 4: Present the dashboard

```
+=====================================================================+
|                      CODE QUALITY DASHBOARD                         |
|                         {date} — {branch}                           |
+=====================================================================+
| Category        | Score | Status  | Details                        |
|-----------------|-------|---------|--------------------------------|
| Type Safety     |  8/10 | WARN    | 3 warnings, 0 errors           |
| Lint            | 10/10 | PASS    | 0 issues                       |
| Tests           |  9/10 | PASS    | 142/147 pass, 5 skip           |
| Dead Code       |  7/10 | WARN    | 12 unused exports              |
+---------------------------------------------------------------------+
| OVERALL         |  8.5  | HEALTHY |                                |
+=====================================================================+

Top issues (if any):
  [TYPECHECK] src/api/users.ts:42 — Parameter 'id' implicitly has type 'any'
  [DEADCODE]  src/utils/legacy.ts — 4 exports never imported
```

Overall score = average of category scores. Verdict:
- 9-10: EXCELLENT
- 7-8: HEALTHY
- 5-6: FAIR — address warnings before adding more features
- 3-4: POOR — address errors before shipping
- 0-2: CRITICAL — stop and fix now

---

## Step 5: Trend analysis (optional)

Check if previous health snapshots exist in `.context/health/` (or similar local store in the project). If prior data exists, show trends:

```
Trends vs last check:
  Type Safety:  8/10 → 8/10  (=)
  Lint:         9/10 → 10/10 (↑ +1)
  Tests:        7/10 → 9/10  (↑ +2) — 12 new tests added
  Dead Code:    5/10 → 7/10  (↑ +2) — cleaned up 8 exports
```

Save a snapshot to `.context/health/{date}.json` for future trend comparison:
```bash
mkdir -p .context/health
```

Use the Write tool to save `{date}.json` with the scores, counts, and branch name.

---

## Step 6: Recommendations

For each category scoring below 8, provide one concrete action:
- Type Safety: "Run the type-checker and fix the N errors — prioritize the ones in `{hottest file}`"
- Lint: "Run the linter with `--fix` to auto-fix {N} of the warnings"
- Tests: "Add tests for the {N} skipped/failing cases in {file}"
- Dead Code: "Delete the {N} unused exports in {files} — they add maintenance surface"

## Completion Status

Report **DONE** with the dashboard, or **DONE_WITH_CONCERNS** if any category is below 6.
