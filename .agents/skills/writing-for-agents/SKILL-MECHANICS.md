# Skill mechanics

## Entrypoint

`SKILL.md` needs `name` and a discriminating `description`. The description is the always-loaded
context pointer: state the capability, real trigger branches, and a boundary only when it prevents
likely misrouting.

Keep common actions and constraints in `SKILL.md`. Put substantial conditional procedures,
formats, or examples in linked resources, and state when the agent should load each one.

## Invocation

Yoke records invocation in `canon/manifest.yaml`:

- `auto` allows provider-supported automatic selection and explicit user invocation.
- `manual` excludes automatic advertising and requires explicit invocation.

Choose `auto` when an agent or another workflow must discover the capability. Choose `manual` when
only a user should select it and the cognitive cost is intentional. Provider metadata is generated
by Retrofit; do not add provider-specific policy to a normal Canon package.

## Validation

The package must remain self-contained. Every relative Markdown link resolves inside the package,
symlinks and path escapes are rejected, and resources install for every supported provider. Test
observable routing or output behavior rather than only matching headings.
