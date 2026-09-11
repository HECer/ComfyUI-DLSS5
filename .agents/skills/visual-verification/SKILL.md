---
name: visual-verification
description: Use for any UI/web project — make the verify gate cover more than unit tests by composing a pipeline (types → unit → design-scan → flow-smoke) and running the built-in yoke flow-smoke gate (landmark + zero console errors + screenshot proof to .yoke/proof/<story>/, video kept on failure). Catches the unwired-page / runtime-crash / AI-slop bugs unit tests miss.
---

# Visual verification

Unit tests don't see a blank page, an unwired route, a runtime console error, or AI-slop design.
Make the loop's gate catch them by widening `verify`, since the loop trusts verify as truth.

## 1. Compose the verify pipeline

Set `verify.command` (in `.yoke/config.yaml`) to chain, fail-fast:

```
<typecheck> && <unit tests> && yoke design-scan . && yoke flow-smoke .
```
e.g. `tsc --noEmit && vitest run && yoke design-scan . && yoke flow-smoke .`. Any red step blocks the story.

## 2. Flow-smoke with the built-in gate

Configure the key user flows once in `.yoke/config.yaml`:

```yaml
smoke:
  baseUrl: http://localhost:3000
  flows:
    - name: home
      path: /
      landmark: "main h1"
    - name: login
      path: /login
      landmark: "form"
```

With that in place, the `yoke flow-smoke .` step from the section-1 pipeline is live.
`yoke flow-smoke` loads each route against the running dev server, waits for the landmark,
fails on any console error, and **always** saves a screenshot to `.yoke/proof/<story>/`
(the loop labels the folder with the current story id via `YOKE_STORY`; standalone runs use
`latest`, or pass `--label=`). Requires Playwright in the project:
`npm i -D playwright && npx playwright install chromium`. Start the dev server before verify
(e.g. via `start-server-and-test`).

## 3. Video only when necessary

`yoke flow-smoke` records video per flow and keeps it **only on failure**
(`.yoke/proof/<story>/<flow>.webm`). When a flow goes red: watch that clip first, then use the
wired Playwright MCP to reproduce interactively. Never record every run manually — the gate
already handles the failure case.

## Rule

Green pipeline = types + units + no design-slop over budget + every flow renders without
console errors, with a screenshot to prove it. Only then is the story actually done.
