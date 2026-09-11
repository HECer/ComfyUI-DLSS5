---
name: codebase-design
description: Design or improve deep modules, small interfaces, real seams, and public-interface tests. Use when shaping a module, placing a dependency seam, evaluating shallow pass-through layers, improving testability, or comparing architecture alternatives; do not force unrelated refactors.
---

# Codebase design

Design deep modules: substantial behavior behind a small interface, placed at a real seam and
tested through that interface. Optimize for caller leverage and maintainer locality.

## Vocabulary

- **Module:** anything with one interface and an implementation, from a function to a package.
- **Interface:** everything a caller must know: types, invariants, ordering, errors, configuration,
  and relevant performance behavior.
- **Implementation:** the behavior hidden inside a module.
- **Depth:** useful behavior per unit of interface a caller must learn.
- **Seam:** a place where behavior can change without editing the caller at that place.
- **Adapter:** a concrete implementation that satisfies an interface at a seam.
- **Leverage:** capability callers gain from a small interface.
- **Locality:** change, knowledge, bugs, and verification concentrated in one place.

Use these terms consistently. Prefer **seam** over the overloaded word **boundary** when discussing
replaceable behavior.

## Design checks

- Reduce methods and parameters when callers do not need the exposed choice.
- Hide repeated orchestration, invariants, and error handling inside the module.
- Apply the deletion test: deleting a useful module should make its complexity reappear across its
  callers. A layer whose complexity simply vanishes was probably a pass-through.
- Treat the interface as the test surface. Tests should survive internal refactors.
- Accept dependencies at real seams instead of constructing hard-to-replace externals internally.
- Introduce a seam for demonstrated variation. Production plus a meaningful test adapter can make
  two real adapters; a single speculative adapter does not.
- Return observable results where practical instead of requiring tests to inspect internal state.

For dependency-specific deepening, read [DEEPENING.md](DEEPENING.md). For a consequential interface
with several plausible shapes, read [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md).
