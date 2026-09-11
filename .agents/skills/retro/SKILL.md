---
name: retro
description: |
  Weekly engineering retrospective. Analyzes commit history, work patterns, and code quality
  metrics for the time window. Team-aware: identifies the user, then analyzes every
  contributor with per-person praise and growth opportunities.
  Use when asked for a "retro", "engineering retrospective", or "weekly summary".
triggers:
  - retro
  - engineering retrospective
  - weekly retro
  - weekly summary
---

# Engineering Retrospective

You are running the `retro` skill. Generate a comprehensive engineering retrospective analyzing commit history, work patterns, and code quality metrics.

## Arguments

- (none) — default: last 7 days
- `24h` — last 24 hours
- `14d` — last 14 days
- `30d` — last 30 days
- `compare` — compare current window vs prior same-length window
- `compare 14d` — compare with explicit window

## Instructions

Parse the argument to determine the time window. Default to 7 days if no argument given. All times should be reported in the user's **local timezone** (use the system default — do NOT set `TZ`).

**Midnight-aligned windows:** For day (`d`) and week (`w`) units, compute an absolute start date at local midnight, not a relative string. For example, if today is 2026-03-18 and the window is 7 days: the start date is 2026-03-11. Use `--since="2026-03-11T00:00:00"` for git log queries — the explicit `T00:00:00` suffix ensures git starts from midnight. For week units, multiply by 7 to get days. For hour (`h`) units, use `--since="N hours ago"`.

**Argument validation:** If the argument doesn't match a number followed by `d`, `h`, or `w`, or the word `compare` (optionally followed by a window), show usage and stop:
```
Usage: retro [window | compare]
  retro              — last 7 days (default)
  retro 24h          — last 24 hours
  retro 14d          — last 14 days
  retro 30d          — last 30 days
  retro compare      — compare this period vs prior period
  retro compare 14d  — compare with explicit window
```

### Step 1: Gather Raw Data

First, fetch origin and identify the current user:
```bash
git fetch origin <default> --quiet
git config user.name
git config user.email
```

The name returned by `git config user.name` is **"you"** — the person reading this retro. All other authors are teammates.

Run ALL of these git commands in parallel (they are independent):

```bash
# 1. All commits in window with timestamps, subject, hash, author, files changed
git log origin/<default> --since="<window>" --format="%H|%aN|%ae|%ai|%s" --shortstat

# 2. Per-commit test vs total LOC breakdown with author
git log origin/<default> --since="<window>" --format="COMMIT:%H|%aN" --numstat

# 3. Commit timestamps for session detection and hourly distribution (with author)
git log origin/<default> --since="<window>" --format="%at|%aN|%ai|%s" | sort -n

# 4. Files most frequently changed (hotspot analysis)
git log origin/<default> --since="<window>" --format="" --name-only | grep -v '^$' | sort | uniq -c | sort -rn

# 5. PR/MR numbers from commit messages (GitHub #NNN, GitLab !NNN)
git log origin/<default> --since="<window>" --format="%s" | grep -oE '[#!][0-9]+' | sort | uniq

# 6. Per-author file hotspots (who touches what)
git log origin/<default> --since="<window>" --format="AUTHOR:%aN" --name-only

# 7. Per-author commit counts (quick summary)
git shortlog origin/<default> --since="<window>" -sn --no-merges

# 8. TODOS.md backlog (if available)
cat TODOS.md 2>/dev/null || true

# 9. Test file count
find . -name '*.test.*' -o -name '*.spec.*' -o -name '*_test.*' -o -name '*_spec.*' 2>/dev/null | grep -v node_modules | wc -l

# 10. Regression test commits in window
git log origin/<default> --since="<window>" --oneline --grep="test:" --grep="regression"

# 11. Test files changed in window
git log origin/<default> --since="<window>" --format="" --name-only | grep -E '\.(test|spec)\.' | sort -u | wc -l
```

### Step 2: Compute Metrics

Calculate and present these metrics in a summary table:

| Metric | Value |
|--------|-------|
| **Features shipped** (from CHANGELOG + merged PR titles) | N |
| Commits to main | N |
| Weighted commits (commits × avg files-touched, capped at 20 per commit) | N |
| Contributors | N |
| PRs merged | N |
| **Logical SLOC added** (non-blank, non-comment — primary code-volume metric) | N |
| Raw LOC: insertions | N |
| Raw LOC: deletions | N |
| Raw LOC: net | N |
| Test LOC (insertions) | N |
| Test LOC ratio | N% |
| Version range | vX.Y.Z → vX.Y.Z |
| Active days | N |
| Detected sessions | N |
| Avg raw LOC/session-hour | N |
| Test Health | N total tests · M added this period · K regression tests |

**Metric order rationale:** features shipped leads — what users got. Commits and weighted commits reflect intent-to-ship. Logical SLOC added reflects real new functionality. Raw LOC is demoted to context because AI inflates it.

Then show a **per-author leaderboard** immediately below:

```
Contributor         Commits   +/-          Top area
You (name)               32   +2400/-300   src/services/
alice                    12   +800/-150    app/api/
bob                       3   +120/-40     tests/
```

Sort by commits descending. The current user (from `git config user.name`) always appears first, labeled "You (name)".

**Backlog Health (if TODOS.md exists):** Compute:
- Total open TODOs (exclude items in `## Completed` section)
- P0/P1 count (critical/urgent items)
- P2 count (important items)
- Items completed this period (items in Completed section with dates within the retro window)

Include in the metrics table:
```
| Backlog Health | N open (X P0/P1, Y P2) · Z completed this period |
```

### Step 3: Commit Time Distribution

Show hourly histogram in local time using bar chart:

```
Hour  Commits
 00:    4      ████
 07:    5      █████
 ...
```

Identify and call out:
- Peak hours
- Dead zones
- Whether pattern is bimodal (morning/evening) or continuous
- Late-night coding clusters (after 10pm)

### Step 4: Work Session Detection

Detect sessions using **45-minute gap** threshold between consecutive commits. For each session report:
- Start/end time (local timezone)
- Number of commits
- Duration in minutes

Classify sessions:
- **Deep sessions** (50+ min)
- **Medium sessions** (20-50 min)
- **Micro sessions** (<20 min, typically single-commit fire-and-forget)

Calculate:
- Total active coding time (sum of session durations)
- Average session length
- LOC per hour of active time

### Step 5: Commit Type Breakdown

Categorize by conventional commit prefix (feat/fix/refactor/test/chore/docs). Show as percentage bar:

```
feat:     20  (40%)  ████████████████████
fix:      27  (54%)  ███████████████████████████
refactor:  2  ( 4%)  ██
```

Flag if fix ratio exceeds 50% — this signals a "ship fast, fix fast" pattern that may indicate review gaps.

### Step 6: Hotspot Analysis

Show top 10 most-changed files. Flag:
- Files changed 5+ times (churn hotspots)
- Test files vs production files in the hotspot list
- VERSION/CHANGELOG frequency (version discipline indicator)

### Step 7: PR Size Distribution

From commit diffs, estimate PR sizes and bucket them:
- **Small** (<100 LOC)
- **Medium** (100-500 LOC)
- **Large** (500-1500 LOC)
- **XL** (1500+ LOC)

### Step 8: Focus Score + Ship of the Week

**Focus score:** Calculate the percentage of commits touching the single most-changed top-level directory. Higher score = deeper focused work. Lower score = scattered context-switching. Report as: "Focus score: 62% (src/services/)"

**Ship of the week:** Auto-identify the single highest-LOC PR in the window. Highlight it:
- PR number and title
- LOC changed
- Why it matters (infer from commit messages and files touched)

### Step 9: Team Member Analysis

For each contributor (including the current user), compute:

1. **Commits and LOC** — total commits, insertions, deletions, net LOC
2. **Areas of focus** — which directories/files they touched most (top 3)
3. **Commit type mix** — their personal feat/fix/refactor/test breakdown
4. **Session patterns** — when they code (their peak hours), session count
5. **Test discipline** — their personal test LOC ratio
6. **Biggest ship** — their single highest-impact commit or PR in the window

**For the current user ("You"):** This section gets the deepest treatment. Include all the detail from the solo retro — session analysis, time patterns, focus score. Frame it in first person: "Your peak hours...", "Your biggest ship..."

**For each teammate:** Write 2-3 sentences covering what they worked on and their pattern. Then:

- **Praise** (1-2 specific things): Anchor in actual commits. Not "great work" — say exactly what was good.
- **Opportunity for growth** (1 specific thing): Frame as a leveling-up suggestion, not criticism. Anchor in actual data.

**If only one contributor (solo repo):** Skip the team breakdown — the retro is personal.

**If there are Co-Authored-By trailers:** Parse `Co-Authored-By:` lines in commit messages. Credit those authors for the commit alongside the primary author. Note AI co-authors (e.g., `noreply@anthropic.com`) but do not include them as team members — instead, track "AI-assisted commits" as a separate metric.

### Step 10: Week-over-Week Trends (if window >= 14d)

If the time window is 14 days or more, split into weekly buckets and show trends:
- Commits per week (total and per-author)
- LOC per week
- Test ratio per week
- Fix ratio per week
- Session count per week

### Step 11: Streak Tracking

Count consecutive days with at least 1 commit to origin/<default>, going back from today.

```bash
# Team streak: all unique commit dates (local time) — no hard cutoff
git log origin/<default> --format="%ad" --date=format:"%Y-%m-%d" | sort -u

# Personal streak: only the current user's commits
git log origin/<default> --author="<user_name>" --format="%ad" --date=format:"%Y-%m-%d" | sort -u
```

Count backward from today — how many consecutive days have at least one commit? Display both:
- "Team shipping streak: 47 consecutive days"
- "Your shipping streak: 32 consecutive days"

### Step 12: Load History & Compare

Before saving the new snapshot, check for prior retro history:

```bash
ls -t .context/retros/*.json 2>/dev/null
```

**If prior retros exist:** Load the most recent one using the Read tool. Calculate deltas for key metrics and include a **Trends vs Last Retro** section:
```
                    Last        Now         Delta
Test ratio:         22%    →    41%         ↑19pp
Sessions:           10     →    14          ↑4
LOC/hour:           200    →    350         ↑75%
Fix ratio:          54%    →    30%         ↓24pp (improving)
```

**If no prior retros exist:** Skip the comparison and append: "First retro recorded — run again next week to see trends."

### Step 13: Save Retro History

After computing all metrics, save a JSON snapshot to `.context/retros/`:

```bash
mkdir -p .context/retros
# Filename: {today}-{sequence}.json
```

Use the Write tool to save with this schema:
```json
{
  "date": "2026-03-08",
  "window": "7d",
  "metrics": {
    "commits": 47,
    "contributors": 3,
    "prs_merged": 12,
    "insertions": 3200,
    "deletions": 800,
    "net_loc": 2400,
    "test_loc": 1300,
    "test_ratio": 0.41,
    "active_days": 6,
    "sessions": 14,
    "deep_sessions": 5,
    "avg_session_minutes": 42,
    "loc_per_session_hour": 350,
    "feat_pct": 0.40,
    "fix_pct": 0.30,
    "peak_hour": 22,
    "ai_assisted_commits": 32
  },
  "authors": {
    "Alice": { "commits": 32, "insertions": 2400, "deletions": 300, "test_ratio": 0.41, "top_area": "src/" }
  },
  "version_range": ["1.16.0", "1.16.1"],
  "streak_days": 47,
  "tweetable": "Week of Mar 1: 47 commits (3 contributors), 3.2k LOC, 38% tests, 12 PRs, peak: 10pm"
}
```

Only include `backlog` if TODOS.md exists. Only include `test_health` if test files were found.

### Step 14: Write the Narrative

Structure the output as:

---

**Tweetable summary** (first line, before everything else):
```
Week of Mar 1: 47 commits (3 contributors), 3.2k LOC, 38% tests, 12 PRs, peak: 10pm | Streak: 47d
```

## Engineering Retro: [date range]

### Summary Table
(from Step 2)

### Trends vs Last Retro
(from Step 12, if prior retros exist — skip if first retro)

### Time & Session Patterns
(from Steps 3-4)

Narrative interpreting what the team-wide patterns mean:
- When the most productive hours are and what drives them
- Whether sessions are getting longer or shorter over time
- Estimated hours per day of active coding (team aggregate)

### Shipping Velocity
(from Steps 5-7)

Narrative covering:
- Commit type mix and what it reveals
- PR size distribution and what it reveals about shipping cadence
- Fix-chain detection (sequences of fix commits on the same subsystem)

### Code Quality Signals
- Test LOC ratio trend
- Hotspot analysis (are the same files churning?)

### Test Health
- Total test files: N (from command 9)
- Tests added this period: M (from command 11)
- Regression test commits: commits matching test: or regression patterns
- If test ratio < 20%: flag as growth area — "100% test coverage is the goal. Tests make coding safe."

### Focus & Highlights
(from Step 8)
- Focus score with interpretation
- Ship of the week callout

### Your Week (personal deep-dive)
(from Step 9, for the current user only)

This is the section the user cares most about. Include:
- Their personal commit count, LOC, test ratio
- Their session patterns and peak hours
- Their focus areas
- Their biggest ship
- **What you did well** (2-3 specific things anchored in commits)
- **Where to level up** (1-2 specific, actionable suggestions)

### Team Breakdown
(from Step 9, for each teammate — skip if solo repo)

### Top 3 Team Wins
Identify the 3 highest-impact things shipped in the window across the whole team. For each:
- What it was
- Who shipped it
- Why it matters (product/architecture impact)

### 3 Things to Improve
Specific, actionable, anchored in actual commits. Mix personal and team-level suggestions. Phrase as "to get even better, the team could..."

### 3 Habits for Next Week
Small, practical, realistic. Each must be something that takes <5 minutes to adopt. At least one should be team-oriented.

### Week-over-Week Trends
(if applicable, from Step 10)
