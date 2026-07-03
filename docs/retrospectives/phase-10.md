# Phase 10 Retrospective: SlotSense UI Redesign + PWA

**Status:** Complete
**Duration:** ~1 week calendar; intensive development July 2026
**PR range:** #48 – #73 (26 PRs)
**ADRs added:** 0028 (Frontend Design System and Theming), 0029 (PWA Co-Branding Hierarchy)
**Final state:** 238 frontend tests across 37 test files; design system live; PWA installable on iOS and Android; 28 automated axe-core scans clean; keyboard/focus-trap verified

---

## What this phase was

Phase 10 took the SlotSense frontend from "functional but visually plain" to
"portfolio-quality" — a genuine consumer product that residents would
install and use daily. At the end of Phase 9, the frontend had 107 tests and
a working AI agent, but it was unstyled React: no component library, no
typographic hierarchy, no mobile layout, no dark mode, no PWA install
experience. Phase 10 changed that.

The phase was designed in two structural parts. The first (10.1–10.4) chose
and installed the design system: Tailwind v4 + shadcn/ui (Radix primitives)
+ lucide-react, mapped onto the existing branding-token contract so that
per-tenant color customization continued to work. The second (10.5–10.9) was
discovery-driven: sub-phases were defined in response to what live testing and
measurement revealed, not from a pre-planned list.

---

## What shipped

### The design system (Phase 10.1–10.3)

Tailwind v4 via `@tailwindcss/vite` (no config file), shadcn/ui components
copied into the repo (not a runtime dependency — no lock-in), Radix primitives
for accessible interactive components, and Inter as the UI typeface via
`@fontsource` (self-hosted). The token architecture deliberately preserved the
existing `--color-*` CSS variable contract and mapped the new system on top —
so `branding.ts` and the `TenantBranding` admin UI required zero changes.

All 14 page-level surfaces were restyled across five PRs (10.3a–10.3e),
working flow-by-flow: auth → resident core → assistant/availability →
tenant-admin → platform-admin. Every page kept its existing semantic structure
(headings, roles, labels), so the 107 pre-existing tests survived the redesign
without modification.

### Dark mode (Phase 10.2c)

First-class dark mode via a `data-mode` attribute on `<html>`, toggled by a
`themeMode.ts` utility that also stores the preference. Because the design
system was CSS-variable-driven from the start, light/dark switching was
largely "free" — most of the work was verifying neutral-token inversion and
fixing a small number of contrast issues discovered in testing.

### PWA install (Phase 10.4, 10.7–10.9)

PWA manifest renamed from the old `"SportSlot"` to `"SlotSense"`, with
placeholder icons replaced by real generated assets (192×192 maskable,
512×512). Service worker configured via Workbox (`registerType: "autoUpdate"`)
with correct cache freshness rules: `no-cache` on `index.html`,
`manifest.webmanifest`, and `sw.js` so deployments are picked up immediately;
`max-age=31536000, immutable` on content-hashed JS/CSS assets. An always-on
install banner with platform-aware wording (iOS vs. Android vs. desktop) was
added to drive active installation.

### Co-branding and layout density (Phase 10.6)

Phase 10.6 was the longest sub-phase — ten PRs (10.6a through 10.6j). It
established the `SlotSenseWordmark` component, the "powered by SlotSense"
footer (ADR-0029), the `ListRow` system for consistent item rendering, a
responsive facility grid, the sticky footer on the assistant page, and a
series of measurement-driven density improvements. This sub-phase also caught
and fixed a backend/frontend mismatch in `MyBookings` (PR #65) where
client-side date filtering was dropping valid upcoming bookings for residents
in non-UTC timezones.

### Accessibility audit (Phase 10.5)

A dedicated audit pass using `jest-axe` + vitest/jsdom across all 14 key
pages in both light and dark mode (28 total scans). Two confirmed structural
violations were found and fixed: unlabeled `<input type="color">` pickers in
`TenantBranding` (labels existed but had no `htmlFor`/`id` association) and
an unlabeled `<input type="file">` in `TenantUsers`. Keyboard navigation was
verified through the full booking flow; Radix's `FocusScope` was confirmed
(not assumed) to trap focus in `ConfirmDialog`. Slot states (available/booked/
past) were verified as text-annotated, not color-only.

---

## What went well

### The protocol held under real aesthetic pressure

The hardest thing about a UI phase isn't the code — it's resisting the
temptation to make judgment calls about visual quality without measurement.
The protocol ("diagnose before fix; measure before change") was violated
exactly once (a padding tweak attempted by feel) and corrected the same
PR via Playwright screenshots. Every other density change after Phase 10.6b
was grounded in computed style inspection or screenshot comparison.

The discipline matters because aesthetic judgment under time pressure
consistently points in the wrong direction. The density saga described below
is evidence of this.

### The booking bug was caught from two directions simultaneously

In PR #65, the same booking-display discrepancy was caught both by the
resident-facing `MyBookings` page (confirmed bookings disappearing for
same-day or past-day bookings depending on the viewer's UTC offset) and
by the agent's `list_my_bookings` tool (which correctly returned the
booking because it queried the backend directly). Having two code paths
produce different answers made the bug immediately suspicious rather than
something to dismiss as "probably a data issue."

The fix — remove client-side date filtering from `useMyBookings` and let
the backend return exactly the right set — was also the right architectural
decision (the backend is the single source of truth for "upcoming" bookings,
because it knows the tenant's timezone and the booking's `cancellable` state).

### The a11y audit was audit-first, not fix-first

Phase 10.5 was explicitly designed as a measurement pass, not an improvement
sprint. The directive was: scan, collect results, fix only confirmed violations.
This avoided two failure modes: (1) "improving" things that already pass and
introducing regressions, and (2) retrofitting vague best-practice annotations
that don't correspond to actual axe violations.

Two confirmed violations were found and fixed with surgical precision. The
keyboard and focus-trap tests confirmed that Radix was delivering the expected
behavior — which is evidence about the library, not just the app.

---

## What went poorly

### The density saga: ~10 rounds to converge on spacing that was a geometry problem

Phase 10.6 accumulated ten sub-phases (10.6a through 10.6j). Most were
productive additions (list row system, responsive grid, co-branding), but
three or four rounds — 10.6b, 10.6c, 10.6d, and part of 10.6i — were
re-attempts at the same problem: facility list items that looked "too tall"
or "too padded" despite multiple padding adjustments.

**The actual problem** was diagnosed in 10.6d: the `ListRow` card wrapper
had a `min-height` constraint inherited from an initial design that made
cards taller than their content regardless of padding. Adjusting `p-4` to
`p-2` did nothing because the height was set by `min-height`, not by
content + padding. Every round that tried to fix this by adjusting padding
was working in the wrong dimension.

**The lesson:** when a container is taller than its content and adding/removing
padding makes no visible difference, the cause is almost certainly layout
geometry (`min-height`, `height`, `flex-basis`, `box-sizing`), not spacing
utilities. The correct diagnostic is: inspect computed styles (height,
min-height, box-sizing) before touching padding/margin. A Playwright screenshot
with annotated element bounds confirms this faster than reading code.

This lesson is now standard diagnostic practice: if a spacing change has no
visible effect, check geometry first.

### "Merged ≠ deployed ≠ deployed correctly": three separate states

PRs #69 and #70 revealed a gap in post-merge discipline. PR #68 (Phase 10.7)
added cache-control headers to `firebase.json` via the Firebase Hosting REST
API. The PR merged and CI passed — but two subsequent PRs were required to fix
the actual deployment:

- **PR #69** fixed a Firebase Hosting REST API schema bug: the `headers` field
  expected an array of `{ key: string, value: string }` objects, not plain
  objects. The REST API accepted the payload silently and deployed without the
  headers, with no error response.
- **PR #70** fixed a path-matching bug: `source: "/"` and
  `source: "/index.html"` are distinct rules in Firebase Hosting. The
  `no-cache` rule was applied to `"/index.html"` but the SPA root is served
  at `"/"`. The cache-control header was not applied to the actual navigation
  request.

Neither problem was visible from the CI log. Both required cache-busted `curl`
requests to the live URL to observe.

**The lesson:** deployment verification is a distinct step from CI passing.
The now-standard post-merge verification checklist is:

1. `gh run list --branch main --limit 3` — confirm the deploy workflow
   completed (not just the test/lint workflow).
2. `curl -sI "https://sport-slot-dev.web.app/index.html?cb=$(date +%s)" | grep -i cache-control` — confirm the expected headers are present on the live URL.
3. If the change involves Hosting configuration: check the Firebase Console's
   Hosting release list to confirm the new config was applied.

"Merged into main" means the code is correct. "Deployed" means the deploy
workflow finished. "Deployed correctly" means the live URL behaves as expected.
These are three separate states and need three separate checks.

### Tailwind v4 `--spacing` scale: `p-4` is 32px, not 16px

When Tailwind v4 was installed (Phase 10.2a), the spacing utilities were
applied as if they were Tailwind v3 (where `p-4 = 1rem = 16px`). In v4, the
spacing utilities multiply by the `--spacing` design token (`--spacing: 0.25rem`
in v3's implicit model becomes `--spacing: 8px` with Tailwind's `@theme`
block). With an 8px base, `p-4 = 4 × 8px = 32px` — double what the v3
muscle-memory said it should be.

This didn't cause failures — the tests don't assert on padding values — but
it was the source of several rounds of "this looks too padded" that preceded
the density saga. The layouts were applying double the intended padding.

**The lesson:** when adopting Tailwind v4, re-anchor your mental model of
spacing utilities. `p-2 = 16px`, `p-4 = 32px`, `p-6 = 48px`. If something
looks padded, don't remove `p-4` and add `p-2` expecting 12px of reduction —
you are reducing by 16px. Use browser DevTools computed-style panel to read
actual pixel values before making changes.

---

## Process improvements adopted

### Diagnose-before-fix as standing discipline

Adopted formally during Phase 10.6i: no spacing or layout change is made
without first reading the computed style of the element in question.
Playwright is available as a diagnostic tool (not just for tests) — a
throwaway script that takes a screenshot with element bounds annotated is
faster than iterating blindly in code.

### Batch-verify with text checklists

Phase 10.5 introduced a pattern: before declaring a sub-phase complete,
verify all items in a pre-written list, not just the items that were worked
on. The axe-core audit verified 28 page-mode combinations even though only 2
pages had violations. This caught nothing unexpected, but the process is the
point — the absence of unexpected violations is evidence, not an assumption.

### Post-merge deployment verification (three states)

Described above. Now applied after any PR that touches `firebase.json`,
`vite.config.ts`, CI workflows, or Cloud Run service configuration.

### Dark-mode testing as a matter of course

After the back-link contrast issue was found in Phase 10.7 (a link that was
readable in light mode but invisible in dark mode), dark-mode testing was
added to the standard review checklist for any component that renders with
`text-*` color utilities.

---

## What Phase 10 produced, in numbers

| Metric | Before Phase 10 | After Phase 10 |
|--------|----------------|----------------|
| Frontend tests | 107 | 238 |
| Test files | — | 37 |
| Design system | None (hand-rolled CSS) | Tailwind v4 + shadcn + Radix |
| Dark mode | No | Yes (data-mode, FOUC-free) |
| PWA installable | No (stale manifest) | Yes (iOS + Android verified) |
| Automated a11y scans | 0 | 28 (14 pages × 2 modes) |
| Confirmed a11y violations | — | 3 found, 3 fixed |
| ADRs | 28 | 29 |

---

## Phase 10 by PR

| PR | Scope |
|----|-------|
| #48 | ADR-0028 — Frontend Design System and Theming |
| #49 | Phase 10.2a — Tailwind v4 + shadcn token foundation |
| #50 | Phase 10.2b — shadcn primitives + AppHeader/ConfirmDialog restyle |
| #51 | Phase 10.2c — responsive shell, dark mode, Inter |
| #52 | Phase 10.3a — auth flow restyle + Inter cleanup |
| #53 | Phase 10.3b — resident Facilities/Account restyle + auth density |
| #54 | Phase 10.3c — SlotGrid, FacilityAvailability, MyBookings restyle |
| #55 | Phase 10.3d — tenant-admin pages restyle |
| #56 | Phase 10.3e — platform-admin pages restyle |
| #57 | Phase 10.4 — PWA manifest rename + placeholder icons + favicon |
| #58 | Phase 10.6a — app icon + SlotSense wordmark + footer co-branding |
| #59 | Phase 10.6b — density + layout polish |
| #60 | Phase 10.6c — root card density + sticky footer + platform name + assistant icon |
| #61 | Phase 10.6d — facility list as plain rows + change-password close |
| #62 | Phase 10.6e — responsive multi-column facility grid |
| #63 | Phase 10.6g — standard ListRow system app-wide |
| #64 | Phase 10.6h — password eye, valid prompts, back-links, chat footer |
| #65 | Booking fix — MyBookings/agent agree; cancel on inactive facilities |
| #66 | Phase 10.6i — measurement-driven padding/width/back-link optimization |
| #67 | Phase 10.6j — back-link visibility, assistant footer, button overlap |
| #68 | Phase 10.7 — SW cache headers, install prompt, facility sort, back-link contrast |
| #69 | Deploy fix — correct Firebase Hosting REST API headers schema |
| #70 | Hosting fix — explicit source:"/" cache-control rule |
| #71 | Phase 10.8 — FOUC fix, hamburger overflow fix, always-on install banner |
| #72 | Phase 10.9 — dark-mode toggle into menu; install banner clarity |
| #73 | Phase 10.5 — axe-core a11y audit; fix unlabeled color/file inputs |

---

## Phase 10 ADRs

- **ADR-0028** — Frontend Design System and Theming (Tailwind v4, shadcn/Radix, token mapping, dark mode, destructive-action posture)
- **ADR-0029** — PWA Co-Branding Hierarchy (tenant-primary/SlotSense-secondary; manifest-name tension; forward-binding for notifications and email)

---

## Honest reflections

Phase 10 was the right phase to do after Phase 9, and not only for portfolio
reasons. The Phase 9 frontend was functional in the sense that every feature
worked — but it wasn't a product anyone would want to use daily. The design
system phase changed that.

The main thing this phase taught is that UI work has a different failure
pattern than backend work. Backend failures are typically loud — a test fails,
an exception is thrown, a contract is violated. UI failures are silent — the
layout looks almost right, the spacing seems slightly off, the dark mode
almost works. Silent failures accumulate and compound; by the time the problem
is obviously visible, you've often been adjusting the wrong thing for several
rounds.

The discipline that works is exactly what the protocol imposes: measure first,
read computed styles, take screenshots, then change. The density saga is a
case study in what happens when that discipline slips — not catastrophically,
but expensively. The deploy/cache confusion is a case study in the same thing
applied to infrastructure: "I deployed it" is not a measurement, it's an
assumption. A `curl` with a cache-buster is a measurement.

These lessons are simple. They are also consistently ignored under time
pressure, because taking a screenshot or running a curl feels slower than
just making the change. It isn't. The density saga ran ~10 rounds. The
cache investigation found the bug in one.

---

## Document history

- **2026-07-03:** Initial drafting during Phase 10 administrative closure.
  Author: Chandra Nakkalakunta with AI assistance (Claude Sonnet 4.6).
