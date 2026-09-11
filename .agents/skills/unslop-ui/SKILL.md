---
name: unslop-ui
description: Use when building or reviewing any UI — detect and remove the visual "tells" of AI-generated/vibecoded design (AI-purple gradients, gradient hero text, neon glow, emoji-as-icons, untouched shadcn defaults, centered-hero-plus-three-cards) so the result looks deliberately designed, not machine-default.
---

# Un-slop the UI

AI-built UIs are "recognizable on sight" — a homogeneous look from a handful of default choices.
Before finishing UI work, remove these tells. Run `yoke design-scan .` for the statically
detectable ones, then apply judgement for the structural ones the scanner can't see.

## The ranked tells (and the fix)

- **AI-purple gradients** (the #1 tell) — purple/violet gradients and `#6c5ce7`-family accents.
  → Choose one real brand color with intent; avoid purple-by-default.
- **Gradient hero text** — `bg-clip-text text-transparent` rainbow headings.
  → Solid color + type weight/scale for emphasis.
- **Neon glow** — `0 0 Npx` colored box-shadows / `shadow-[0_0_...]`.
  → Subtle, neutral elevation (small offset, low blur, low opacity).
- **Emoji-as-icons** — 🚀✨🔥 in buttons/nav/feature lists.
  → A real icon set (lucide, etc.), consistent stroke + size.
- **Untouched shadcn/Tailwind defaults** — default radius, default slate everywhere.
  → Set deliberate tokens (radius, spacing scale, one accent) so it doesn't look boilerplate.
- **Centered hero + three feature cards** — the canonical AI landing layout.
  → Vary rhythm: asymmetry, a real product shot, content density that fits the product.
- **Homogeneous spacing / no hierarchy** — everything the same size and gap.
  → Establish a type scale and spacing rhythm; make the primary action obviously primary.

## Rule

Treat `yoke design-scan .` as a gate (it exits non-zero over budget). Fix findings, then
eyeball the structural tells above. Distinctive, intentional > generic-but-safe.

*Rubric informed by the MIT-licensed research in [vibecoded-design-tells](https://github.com/JCarterJohnson/vibecoded-design-tells) (© Carter Johnson). Yoke implements the idea natively; no code/data copied.*
