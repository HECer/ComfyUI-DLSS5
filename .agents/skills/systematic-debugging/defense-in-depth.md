# Defense in depth

Fix the originating contract violation first. Then identify independent trust boundaries where malformed or stale data could enter again: configuration, external process output, persisted state and public interfaces.

Validate at those boundaries with explicit errors and preserve unknown values. Avoid scattering duplicate checks through code that already has a validated type. Do not catch every exception and return success or zero.

Test malformed input, missing evidence, stale state, cancellation and cleanup. For destructive operations verify target scope and authority independently of the requesting model. Protection layers must not weaken acceptance tests or convert a blocked action into an automatic permission bypass.
