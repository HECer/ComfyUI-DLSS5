# Root-cause tracing

Capture the smallest failing command, inputs, expected/actual behavior, environment and code revision. Reproduce before changing code.

Trace backward from the first observed invalid value or state transition to its producer. At each boundary, record the input, output and contract without logging credentials. Distinguish a downstream symptom from the earliest violated invariant.

Form one falsifiable hypothesis and choose an observation that separates it from alternatives. Change one factor at a time. If reproduction depends on concurrency, preserve scheduling and cancellation evidence rather than adding arbitrary delays.

Write a regression test at the violated boundary, demonstrate its failure, fix the cause and run dependent checks. Document remaining uncertainty instead of attributing an intermittent pass to a fix without evidence.
