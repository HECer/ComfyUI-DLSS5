# Condition-based waiting

Prefer a completion event or promise over sleeping for an assumed duration. Subscribe before starting work so a fast completion is not missed. Handle success, failure, cancellation and timeout, and remove listeners/timers in every terminal path.

If polling is unavoidable, choose a measurable condition, bounded deadline and modest interval. Preserve the last observed state in the timeout error. Do not treat repeated log output as successful progress.

Tests should control time or use an explicit readiness signal. Keep one real process integration test where needed. A larger timeout is justified only by measured runtime and does not repair a race or an unintended network call.
