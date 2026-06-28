# ADR-0028: Frontend Design System and Theming

- **Status:** Proposed (2026-06-28) — pending Coordinator acceptance; flip to Accepted on merge
- **Phase:** 10 (UI Redesign + PWA Mobile Validation), sub-phase 10.1
- **Supersedes:** none. **Extends:** ADR-0012 (Frontend architecture), ADR-0013 (Frontend libraries)
- **Deciders:** Coordinator (Chandra), Strategist (Claude Opus 4.8)

## Context

The SlotSense frontend (React 18 + Vite 6 + TS 5.7 PWA on Firebase Hosting, per
ADR-0012/0013) is functional but visually plain. Phase 10 raises it to
portfolio quality across mobile, tablet, and desktop. The redesign is the
highest-leverage portfolio improvement in the roadmap and is sequenced before
production hardening for that reason.

Verified current state (2026-06-28), not assumed:

- **No design system or component library is installed.** `package.json`
  dependencies are React, react-dom, react-router-dom v7, TanStack Query, and
  Firebase only. No Tailwind, Radix, shadcn, MUI/Chakra, or CSS-in-JS.
- **Styling is two hand-rolled files:** `src/styles/theme.css` (global tokens +
  `body`, imported in `main.tsx`) and `src/styles/assistant.css` (page-scoped,
  imported in `Assistant.tsx`).
- **A tenant-theming contract exists and is shipped** (ADR-0012 §4, Phase 4.6).
  `theme.css` declares CSS variables on `:root`:
  `--color-primary #1a4d8f`, `--color-secondary #0f7b6c`,
  `--color-background #ffffff`, `--color-surface #f4f6fa`,
  `--color-text #1c1f26`, `--color-text-muted #5b6472`,
  `--color-danger #b3261e`, `--font-family` (system stack),
  `--radius 8px`, `--spacing 8px`.
- **`src/lib/branding.ts` is the runtime injector.** At login/startup it fetches
  `/api/v1/tenants/{slug}/branding` and runs
  `document.documentElement.style.setProperty("--color-primary" | "--color-secondary", …)`.
  Only those two tokens are tenant-overridable; the rest are global constants.
- **Test suite is restyle-safe.** 107 frontend tests, all Testing-Library
  (role/text queries); `grep toMatchSnapshot` returns 0. A styling redesign that
  preserves semantic structure (roles, labels, headings, text) does not break the
  suite.
- **PWA manifest is stale:** name `"SportSlot"` (pre-rename), `icons: []`,
  `registerType: "autoUpdate"`. Deferred to sub-phase 10.4.

The constraint that shapes this decision is the tenant-theming contract: any
design system adopted must consume runtime-swappable CSS variables, and must not
break the backend branding API, the `TenantBranding` admin UI, or `branding.ts`.

## Decision

### 1. Component-library posture: Tailwind CSS v4 + shadcn/ui (Radix) + lucide-react

- **Tailwind v4** via `@tailwindcss/vite` — config-less `@theme` model, clean fit
  with the existing Vite 6 setup; makes responsive (mobile/tablet/desktop)
  consistent.
- **shadcn/ui** components, copied into the repo (not a runtime dependency), built
  on **Radix primitives** — accessible by default (keyboard, focus, ARIA), which
  serves the 10.5 accessibility audit and keeps Radix's correct roles intact so
  the role/text-based tests survive the redesign.
- **lucide-react** for iconography (MIT, pairs with shadcn).

### 2. Token architecture: preserve the contract, map the system on top

The existing `--color-*` contract remains the **source of truth** for
tenant-brandable colors. `branding.ts` is **unchanged**; the backend branding API
and `TenantBranding` admin UI keep working. The new system is **additive**:

- shadcn/Tailwind's expected tokens are **mapped onto** the existing contract,
  e.g. `--primary: var(--color-primary)`, `--secondary: var(--color-secondary)`,
  `--background: var(--color-background)`, `--card: var(--color-surface)`,
  `--foreground: var(--color-text)`, `--muted-foreground: var(--color-text-muted)`,
  `--destructive: var(--color-danger)`, `--radius: var(--radius)`.
- Tailwind v4's opacity modifier uses `color-mix()`, which consumes `var()` hex
  colors directly — **no hex→HSL conversion is required**, so `branding.ts` does
  not change. (If opacity-on-brand-color ever proves necessary beyond what
  `color-mix()` covers, extending `branding.ts` to also emit HSL-channel
  variables is a contained ~15-line follow-up — deferred, not done now.)
- The system **adds** what the contract lacks: a neutral scale (50–900) anchored
  on the existing `--color-text` / `--color-text-muted`, `success` and `warning`
  roles, and a focus `ring`.

### 3. Brand vs functional colors: a hard split

- **Brand colors** (`primary`, `secondary`) are **tenant-themed** — they carry a
  tenant's identity and are overridden at runtime by `branding.ts`.
- **Functional / semantic colors** (`success` = available, `warning` = peak,
  `muted` = booked/unavailable, `destructive` = cancel/remove, and the neutral
  scale) are **system-controlled and NOT tenant-overridable.**

Rationale: functional color encodes meaning and must stay consistent and
accessible across every tenant. A tenant must not be able to make "available"
unreadable or recolor a destructive action. This is an accessibility and
correctness boundary, not a style preference. Note the default brand secondary
(`#0f7b6c`, teal) and the functional success green are **independent** tokens —
they may rhyme visually but one is themable and one is not.

### 4. Design language: "calm operational confidence"

A tool used daily to book a court — fast, legible, quietly premium, with enough
warmth to read as a neighborhood community product rather than enterprise chrome.
Calibration references: Linear (typographic discipline), Stripe Dashboard (data
legibility), Vercel (clean surfaces).

- **Color:** navy `#1a4d8f` as the default brand anchor (already the manifest
  theme color); functional semantics — available = emerald, peak = amber,
  booked = muted neutral, destructive = red (`#b3261e`). Final stops and WCAG AA
  contrast are verified in 10.2; representative values only here.
- **Typography:** Inter (self-hosted via `@fontsource`, no license burden) for UI
  and body, with **tabular figures** for all times, dates, and quantities — a
  scheduling app depends on numeric alignment. The existing `--font-family`
  contract maps to `--font-sans`.
- **Spacing & shape:** 8px base grid (existing `--spacing`), `--radius` 8px
  (existing), 0.5–1px borders over heavy shadows.
- **Dark mode:** first-class, via a `data-mode`/class strategy. Tenant brand
  colors apply in both modes; neutrals and functional tints flip. Nearly free
  given the CSS-variable architecture, and a strong portfolio signal.

### 5. Destructive-action posture

Destructive actions (e.g. facility "Remove") de-emphasize to ghost/icon controls
that reveal danger styling on hover and confirm on intent — replacing the current
pattern of always-on loud red outline buttons (alarm fatigue, mis-click risk).

## Consequences

**Positive**

- One mechanism satisfies three requirements at once: design tokens, per-tenant
  runtime theming, and accessibility (via Radix).
- No rewrite — the work is additive over a shipped, working contract; lowest-risk
  path that respects existing backend and admin surfaces.
- Restyle is test-safe (0 snapshots; role/text queries); churn is limited to
  where content/structure actually changes.
- Dark mode and consistent responsiveness come largely for free.

**Negative / risks**

- shadcn components are copied in, so they're maintained in-repo (intentional —
  it's the no-lock-in trade).
- 10.2 touches build config (`vite.config`, Tailwind) and global styling — a
  **risk-sensitive PR** (protocol §3.5) requiring full Strategist review.
- `assistant.css` (page-scoped CSS) is absorbed into the component system during
  10.3c; until then the two styling worlds coexist briefly.

**Migration**

- 10.2 establishes Tailwind + shadcn + the token-mapping layer + base primitives +
  the responsive shell, leaving the `--color-*` contract and `branding.ts` intact.
- 10.3 reimplements pages flow-by-flow (auth → resident core → assistant →
  tenant-admin → platform-admin), each its own PR.
- Live-testing rounds during 10.3 surface their own slices (protocol §4.9);
  expected, not slippage.

## Alternatives considered

- **MUI / Chakra / Ant Design** — rejected. They impose their own visual identity,
  add runtime dependency weight, and fight bespoke per-tenant theming — the
  opposite of a portfolio-distinctive look.
- **Keep hand-rolled CSS** — rejected. No accessibility baseline, no scale across
  ~27 surfaces, inconsistent by construction.
- **CSS Modules + Radix, no Tailwind** — rejected. More boilerplate, slower
  iteration, weaker responsive ergonomics; loses Tailwind's utility velocity.
- **Rewrite the theming contract to shadcn's HSL-channel idiom** — rejected. Would
  break `branding.ts`, the branding API, and the admin UI for no benefit
  `color-mix()` doesn't already provide.

## References

- ADR-0012 (Frontend architecture, §4 theming contract), ADR-0013 (Frontend libraries)
- Protocol §3.5 (risk-tiered review), §4.9 (live-testing cadence), §7.5 (ADR discipline)
- `src/styles/theme.css`, `src/lib/branding.ts`, `vite.config.ts`
