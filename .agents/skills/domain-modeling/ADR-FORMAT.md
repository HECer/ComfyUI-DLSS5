# ADR-class decision format

Append a concise entry to `.yoke/context/DECISIONS.md` only when the choice is:

1. hard to reverse;
2. surprising without context; and
3. the result of a real trade-off.

Use this shape:

```md
## YYYY-MM-DD — ADR: Short decision title

Context: one sentence describing the constraint or trade-off.
Decision: one sentence stating the chosen direction and why.
```

Add considered options or consequences only when a future maintainer would otherwise repeat the
same investigation. Easy, obvious, or no-alternative choices stay out of the decision log.
