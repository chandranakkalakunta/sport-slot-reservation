# Changelog

All notable changes to SportSlotReservation are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Phase 10 complete — UI Redesign + PWA + Accessibility (PRs #48–#73, 26 PRs, July 2026)

Phase 10 raised the SlotSense frontend from functional-but-unstyled to
portfolio-quality consumer product. Key outcomes:

- **Design system:** Tailwind v4 + shadcn/ui (Radix primitives) + Inter, mapped
  onto the existing `--color-*` CSS-variable branding contract. All 14 page
  surfaces restyled. Dark mode first-class via `data-mode`/FOUC-free inline
  script. Test count grew from 107 to 238 across 37 test files.
- **PWA:** Real app icons, correct Workbox cache strategy (`no-cache` on
  navigation files, `immutable` on content-hashed assets), always-on install
  prompt with platform-aware wording. Two deploy-pipeline bugs found and fixed
  during rollout (Firebase Hosting REST API schema; `source:"/"` vs.
  `source:"/index.html"` path matching — see PRs #69–#70).
- **Co-branding:** Tenant brand is the dominant app identity; "powered by
  SlotSense" footer is the secondary platform attribution. ADR-0029 captures
  this hierarchy and forward-binds future surfaces (push notifications,
  email, install prompt). Manifest name remains "SlotSense" (install-time
  constraint; per-tenant manifest serving deferred).
- **Booking fix (PR #65):** Removed client-side date filtering in `useMyBookings`
  that was silently dropping confirmed bookings for residents in non-UTC
  timezones. Backend is now the declared single source of truth for the
  "upcoming" booking set.
- **Accessibility audit (Phase 10.5):** 28 automated axe-core scans (14 pages
  × 2 modes) — zero serious/critical violations after fixing two confirmed
  findings (unlabeled color pickers in TenantBranding; unlabeled file input in
  TenantUsers). Keyboard navigation and Radix FocusScope focus-trap confirmed.
- **ADRs:** ADR-0028 (design system + theming) and ADR-0029 (co-branding
  hierarchy).
- **Retrospective:** `docs/retrospectives/phase-10.md` — the density saga,
  deploy/cache lessons, and process improvements adopted.

### Added / Fixed (Phase 10.5 — Accessibility audit, axe-core scan, keyboard & focus-trap verification)

- **Automated axe-core audit added (`src/a11y.audit.test.tsx`):** 44 tests covering all 14 key
  pages (SignIn, Facilities, FacilityAvailability, MyBookings, Account, Assistant,
  TenantDashboard, TenantFacilities, TenantUsers, TenantPolicies, TenantBranding,
  TenantList, CreateTenant, CreateUser) in both light and dark mode via `jest-axe` + vitest/jsdom.
  Zero axe `serious`/`critical` violations after fixes.
- **TenantBranding — two unlabeled `<input type="color">` fixed (confirmed `label` violation):**
  Primary-color and secondary-color pickers had visible `<label>` text but no `htmlFor`/`id`
  association, so screen readers could not announce the label. Added `htmlFor="brand-primary-color"`
  / `id="brand-primary-color"` and the same for secondary. No visual change.
- **TenantUsers — unlabeled `<input type="file">` fixed (confirmed `label` violation):**
  The CSV bulk-import file picker had no accessible name. Added
  `aria-label="Upload CSV for bulk user import"`. No visual change.
- **Keyboard navigation verified:** Tab order confirmed through SignIn (email → password →
  show/hide toggle → submit → Google → forgot-pw), Facilities (facility links reachable),
  FacilityAvailability (date input + available slot buttons reachable; disabled slots
  correctly skipped by Tab), Account (both password fields + submit), MyBookings (Cancel button
  reachable and dialog opens via Enter).
- **ConfirmDialog focus-trap verified (Radix FocusScope):** Focus moves into dialog on open;
  10 Tab cycles stay inside the dialog (trap confirmed); Escape closes dialog and calls onCancel;
  Cancel and Confirm buttons both operable via keyboard.
- **SlotGrid accessible states verified:** Each slot button exposes its time + state text in the
  accessible name (`getByRole("button", { name: /08:00.*available/ })`), so state is not
  color/text-only. Disabled buttons are correctly `disabled`. All three states (available,
  booked, past) have visible text labels.
- **CSS contrast note:** jsdom does not compute CSS custom-property values, so color-contrast
  violations cannot be caught programmatically in this setup. The Phase 10.7 back-link contrast
  fix remains the last known contrast issue; dark-mode token values are unchanged since that fix.
  Manual verification with a real browser (Lighthouse / DevTools) is recommended on each
  token-value change per ADR-0028.
- **dep:** `jest-axe@10.0.0` + `@types/jest-axe@3.5.9` added as devDependencies.
- CI gate: 37 test files, 238 tests green; `pnpm lint` 0 errors; `pnpm build` clean;
  contract diffs empty (TenantBranding.tsx and TenantUsers.tsx — aria attributes only).

### Fixed / Changed (Phase 10.9 — Dark-mode toggle into menu; install banner clarity)

- **Dark-mode toggle relocated to hamburger menu (mobile):** The persistent moon/sun icon in
  the mobile header row (`size-9 = 72px` with `--spacing: 8px`) consumed 88px of brand space
  that is now freed. The toggle is hidden on mobile via `hidden sm:inline-flex` and rendered
  as the first item in the opened mobile nav (Button `ghost sm` with Moon/Sun icon + "Dark
  mode"/"Light mode" label). On desktop (≥640px, no hamburger) it stays in the persistent
  header row — unchanged. Keyboard accessibility, aria-label, and `applyMode()` behavior are
  fully preserved; only the toggle's DOM location on mobile changes.
- **Brand name room improvement:** With only the hamburger (72px) in the mobile right cluster,
  available brand width at 375px grows from 135px to 223px. A tenant with "RVRG Residency"
  (114px text) + 80px logo (218px total) now fits from ~266px viewport onward vs. ~394px
  previously — an 128px improvement in the breakeven width.
- **Install banner wording fix (Android/manual-hint):** The instruction `"Tap ⋮ menu →
  Install app"` was ambiguous — Coordinator confused it with the app's own ☰ hamburger. Fixed
  to `"Open your browser's ⋮ menu → Install app"`, making it unambiguous that the BROWSER's
  three-dot menu is meant (not the app's). Investigation confirmed no logic coupling between
  the Install banner's onClick handler and AppHeader's hamburger state — pure wording issue.
- CI gate: 36 test files, 194 tests green (+3 AppHeader mobile-menu toggle tests); `pnpm lint`
  0 errors; `pnpm build` clean; contract diffs empty.

### Fixed / Added (Phase 10.8 — FOUC fix, hamburger overflow fix, always-on install banner)

- **Dark-mode FOUC fix (index.html):** Added a tiny blocking (non-module) inline `<script>`
  in `<head>` that runs synchronously before any CSS is applied. It reads
  `localStorage.getItem("slotsense-theme")` and `prefers-color-scheme` and sets
  `document.documentElement.dataset.mode = "dark"` immediately if needed. This prevents the
  flash where dark-mode-aware CSS tokens (e.g. `--color-link: #1a4d8f` dark-blue, invisible
  on dark background) resolve to their light-mode values on the first paint. The existing
  `applyMode()` call in `main.tsx` continues to handle subsequent toggles. Wrapped in
  `try/catch` so any localStorage/matchMedia unavailability is silently ignored.
- **Hamburger icon overflow fix (AppHeader.tsx):** With `--spacing: 8px`, the right icon
  cluster (`dark-toggle 72px + gap 16px + hamburger 72px = 160px`) and a `shrink-0` brand
  div together overflow narrow viewports when a wide tenant logo or long brand name is
  configured. Root cause: brand div was `shrink-0` with no min-w-0, preventing compression.
  Fix: removed `shrink-0` from brand div; added `min-w-0` (allows flex shrink); logo `<img>`
  gets `shrink-0 max-w-[80px] object-contain` (capped at 80px, proportional scale); brand
  `<Link>` gets `truncate` (ellipsis if compressed). Hamburger verified in-viewport at
  320/336/375/390/414px via Playwright (with 120px logo + long brand name).
- **Always-on install banner (InstallPrompt.tsx):** The existing banner was gated on
  `beforeinstallprompt` having fired (Chrome engagement heuristic — may never fire on first
  visit). Updated to show unconditionally for any non-standalone session. States: `ready`
  (native prompt available — tapping Install calls `prompt()` directly); `ios-hint` (iOS
  Safari — shows "Tap Share → Add to Home Screen" immediately); `manual-hint` (Android/other
  before engagement — shows Install button; tapping reveals "Tap ⋮ menu → Install app"
  inline). Dismiss persists `slotsense-install-dismissed=1` to localStorage (never-show-again
  policy). Already-installed (standalone) sessions render nothing.
- CI gate: 36 test files, 191 tests green (+10 InstallPrompt tests); `pnpm lint` 0 errors;
  `pnpm build` clean; contract diffs empty.

### Fixed / Added (Phase 10.7 — SW cache freshness, install prompt, facility ordering, back-link dark-mode contrast)

- **SW cache freshness (firebase.json):** Added `headers` section to Firebase Hosting
  config. `index.html`, `manifest.webmanifest`, `sw.js`, `registerSW.js`, and
  `workbox-*.js` all get `Cache-Control: no-cache` so browsers always revalidate on
  load. Content-hashed assets under `/assets/**` keep `public, max-age=31536000,
  immutable` (safe because hash changes on each rebuild). Result: deploys immediately
  serve fresh HTML + SW; hashed assets remain efficiently cached. Effect takes hold
  after the next `firebase deploy`; verify via `curl -sI https://sport-slot-dev.web.app/
  | grep -i cache-control`.
- **SW behavior (proposed, NOT applied):** The current `registerType: "autoUpdate"` with
  `cleanupOutdatedCaches: true` is correct. With the no-cache headers above, the browser
  will fetch a fresh `sw.js` on every load. Workbox already uses `skipWaiting` and
  `clientsClaim` implicitly in `generateSW` mode. No change to SW activation behavior
  is needed or applied.
- **PWA install prompt (Facilities page):** Added `useInstallPrompt` hook
  (`src/hooks/useInstallPrompt.ts`) and `InstallPrompt` component
  (`src/components/InstallPrompt.tsx`). On Android/Chrome: listens for
  `beforeinstallprompt`, stashes it, shows "Install app" button; calls `prompt()` on
  click; hides on `appinstalled`. On iOS Safari (no `beforeinstallprompt`): detects iOS
  UA + not-standalone, shows "Install: tap Share → Add to Home Screen" hint. Already
  installed (standalone `display-mode`) → hidden. Dismissible via × button. Rendered
  above the h1 in the Facilities page (home for residents).
- **Facility ordering:** Both `Facilities` and `TenantFacilities` now sort the active
  facility list by `name` ascending using `localeCompare` before rendering. Sort applied
  in the component (no query change). Order is stable across re-renders.
- **Back-link dark-mode contrast (root cause measured):** After the 10.6j `block` fix,
  back-links are structurally correct (`display: block`, correct margins from
  `space-y-*`). The remaining "invisible" symptom is a WCAG color-contrast failure:
  `text-primary` (#1a4d8f) on the dark-mode background (#0f1115) gives a contrast ratio
  of ~2.25:1 — far below the 4.5:1 AA threshold. Fix: added `--color-link` semantic
  token to `theme.css` (`#1a4d8f` light, `#60a5fa` dark — ~4.6:1 on #0f1115). All
  navigation links (`text-primary underline`) updated to `text-link`. The `block` class
  from 10.6j is preserved on all back-links.
- CI gate: 35 test files, 181 tests green; `pnpm lint` 0 errors; `pnpm build` clean.

### Fixed (Phase 10.6j — Back-link visibility, assistant footer spacing, TenantUsers button overlap)

- **Back-link resize-to-appear bug (all pages):** In Tailwind v4, `space-y-*` applies
  `margin-block-end` via `> :not(:last-child)`. When the first child is an inline `<a>`
  (the back-link), some mobile browsers collapse its effective height on initial paint
  and only correct on resize. Fix: added `block` to every back-link `<Link>` so it is
  always a block-level element — immediate visibility on load, left-aligned with the
  container's padding edge (same as cards below). Affected: `FacilityAvailability`,
  `MyBookings`, `Account` (×2), `TenantFacilities`, `TenantUsers`, `TenantPolicies`,
  `TenantBranding`, `CreateUser`.
- **Assistant footer dead gap:** `paddingBottom: 56` on a `height: 100dvh` element in
  CSS `content-box` mode adds blank space *below* flex content (not above it) — the
  inner div becomes `100dvh + 56 px` tall, and the AuthedLayout `pb-14` (112 px) adds
  another 112 px, totalling `100dvh + 168 px` of page height and a large scrollable
  gap. Fix: changed the outer chat container to `position: fixed; inset: 0` so it is
  exactly viewport-sized with no page overflow; `paddingBottom: 72` (≥ footer height
  ~65 px) ensures the chat input sits just above the fixed footer with ~7 px clearance.
- **TenantUsers two-button overlap (mobile):** The two action buttons ("Issue temp
  password" ~188 px + "Deactivate" ~128 px + gap = ~332 px) exceeded the 326 px
  mobile container. `shrink-0` on the action div prevented shrinking, causing the
  buttons to overlay the user info text. Fix: replaced `ListRow` on user rows with a
  responsive card — `flex-col gap-2` on mobile (info block above, buttons as equal-
  width `flex-1` row below), `sm:flex-row sm:items-center sm:justify-between` on
  desktop. Both buttons keep their exact labels, handlers, and ConfirmDialog flow;
  `min-h-[40px]` ensures ≥ 40 px touch targets at all breakpoints.
- CI gate: 35 test files, 181 tests green; `pnpm lint` 0 errors; `pnpm build` clean.

### Changed (Phase 10.6i — Measurement-driven padding / width / back-link optimization)

- **Discovery:** `theme.css:86` sets `--spacing: 8px`, so Tailwind v4's `p-4` renders as
  32 px (not the 16 px assumed from v3 defaults). All padding changes below use
  measured pixel values as targets.
- fix(frontend): `ListRow` — `p-4` → `p-2` (32 px → 16 px measured) for all list rows
  across MyBookings, TenantFacilities, TenantUsers, TenantList.
- fix(frontend): `ui/card.tsx` — `py-4` → `py-3` (32 px → 24 px) on `Card`;
  `px-6` → `px-3` (48 px → 24 px) on `CardHeader`, `CardContent`, `CardFooter`.
  Narrow ADR-0028 exception — token identities untouched, only spacing values adjusted.
- fix(frontend): `Facilities`, `MyBookings`, `TenantList`, `TenantFacilities`,
  `TenantUsers` — `max-w-5xl` → `max-w-6xl` (1024 px → 1152 px) to reduce
  right-side dead space on wide viewports.
- fix(frontend): `Facilities` — promo card and facility grid tiles `p-4` → `p-2`
  (32 px → 16 px measured).
- fix(frontend): Back-links on all pages that already carried `font-medium text-primary`
  updated to `underline underline-offset-2 hover:text-primary/70` for consistent,
  prominent link affordance. Pages: `FacilityAvailability`, `Account` (×2),
  `ForgotPassword`, `ResetPassword`, `CreateUser`, `TenantBranding`, `TenantPolicies`,
  `TenantFacilities`, `TenantUsers`, `MyBookings`. `ResetPassword` also gained
  previously-missing `font-medium`.
- CI gate: 35 test files, 181 tests green; `pnpm lint` 0 errors; `pnpm build` clean.

### Fixed (Phase 10.6h — Password eye, valid assistant prompts, back-links, chat footer)

- fix(frontend): `ResetPassword` and `ForcePasswordChange` — added show/hide eye
  toggle to both "New password" and "Confirm new password" fields, matching the
  exact `Eye`/`EyeOff` lucide icon + `type="button"` + `aria-label` pattern from
  `SignIn`. States `showPw`/`showConfirm` are independent so each field can be
  revealed separately. Accessible labels: "Show/Hide password" (new-pw field),
  "Show/Hide confirm password" (confirm field).
- fix(frontend): `SuggestedPrompts` — replaced invalid example prompts
  ("What's my usual court?", "Book my usual tennis slot tomorrow",
  "Show my upcoming bookings") with valid booking/availability queries the agent
  actually handles: "Book tennis tomorrow", "Is tennis free today?",
  "Is football available tomorrow?", "Book badminton this Saturday". No agent
  logic changed. `SuggestedPrompts.test.tsx` updated to match new strings.
- fix(frontend): `Facilities` — updated Booking Assistant promo-card example text
  from "book my usual tennis slot" to "book tennis tomorrow" to match actual
  agent capability.
- fix(frontend): All back-links (`← Facilities`, `← Dashboard`, `← Back`,
  `← Back to tenants`, "Back to sign in") across nine pages — added
  `font-medium` to the shared className for clearer, consistent link affordance.
  `CreateUser` also gained `text-sm` (previously missing).
- fix(frontend): `Assistant` — added `paddingBottom: 56` to the outer
  `height: 100dvh` flex container. This reduces the usable column height by 56px
  (matching AuthedLayout's `pb-14`), so the MessageInput area clears the fixed
  "powered by SlotSense" footer without hiding any chat content.
- CI gate: 35 test files, 180 tests green.


### Added (Phase 10.6g — Standard list row system)

- feat(frontend): Introduced `<ListRow>` component (`src/components/ListRow.tsx`)
  as the single source of truth for list row layout: `rounded-lg border bg-card p-4
  flex items-center justify-between gap-3`. Content area gets `min-w-0 flex-1` (enables
  `truncate`); action area gets `flex items-center gap-2 shrink-0` (inline at all
  breakpoints). Accepts `actionClassName` for rows that need tight `flex-wrap`
  (TenantUsers two-button row).
- fix(frontend): `MyBookings`, `TenantFacilities`, `TenantUsers`, `TenantList` — all
  list rows converted to `<ListRow>`. Killed `flex-col gap-3 sm:flex-row sm:items-center
  sm:justify-between` and `self-start/sm:self-auto` patterns. Actions (Cancel,
  Remove, Deactivate, Issue temp password) are now inline at ALL breakpoints. Facility
  name, display name, and tenant name get `truncate` for overflow safety.
- fix(frontend): All five list/grid pages (`Facilities`, `MyBookings`, `TenantFacilities`,
  `TenantUsers`, `TenantList`) — `max-w-3xl` → `max-w-5xl` on main container.
- fix(frontend): `Facilities` — grid breakpoint `sm:grid-cols-2` → `md:grid-cols-2`
  so single-column view persists on small tablets (768px is the new break).
- fix(frontend): `TenantList` — `+ Add admin/user` link promoted from inline content
  to `ListRow` action area; consistent right-aligned placement with all other action rows.
- CI gate: 35 test files, 180 tests green.

### Added (Phase 10.6e — Responsive multi-column facility grid)

- feat(frontend): Facility tiles now lay out in a responsive grid:
  `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3` (1 mobile / 2 tablet / 3
  desktop). Tiles remain plain bordered `<Link>` blocks (no Card) — grid stretch
  gives clean equal-height tiles per row without the dead-space bug. Booking
  Assistant card stays full-width above the grid (not a grid item). `h-full` not
  needed: plain `<Link>` block has no inner flex column; stretch is already clean.
- CI gate: 35 test files, 180 tests green; 0 lint errors; clean build.

### Added (Phase 10.6d — Facility list as plain rows; change-password close)

- fix(frontend): Root cause of tall list rows confirmed: `<div class="grid"> →
  <Card flex flex-col>` where `align-items: stretch` inflated single-child flex
  cards to fill the grid row height. Prior `py-0`/`gap-3` fixes addressed padding
  but not the grid-stretch root.
- fix(frontend): `Facilities.tsx` — converted facility list from `grid → Card →
  CardContent → Link` to plain bordered `<Link>` rows (`space-y-3` stack,
  `rounded-lg border bg-card p-4`), matching the existing Booking Assistant card
  pattern. `Card`/`CardContent` imports removed.
- fix(frontend): `MyBookings.tsx` — converted booking list from `grid → Card →
  CardContent` to plain bordered `<div>` rows (`space-y-2`); mobile stacking
  (flex-col sm:flex-row) and Cancel/Cancellation-closed affordances preserved.
  `Card`/`CardContent` imports removed.
- fix(frontend): `TenantList.tsx` — converted tenant list from `grid → Card →
  CardContent` to plain bordered `<div>` rows; "+ Add admin/user" link preserved.
  `Card`/`CardContent` imports removed.
- fix(frontend): `TenantFacilities.tsx` — converted facility list from
  `grid → Card → CardContent` to plain bordered `<div>` rows; Remove button,
  ConfirmDialog flow, and mobile stacking preserved. `Card`/`CardContent` imports
  removed.
- fix(frontend): `TenantUsers.tsx` — converted user list from `grid → Card →
  CardContent` to plain bordered `<div>` rows; Issue temp password + Deactivate
  buttons, ConfirmDialog flow, and mobile stacking preserved. `Card`/`CardContent`
  imports removed.
- fix(frontend): `Account.tsx` — added `← Back` link to `/` on the Change password
  form so users can exit without submitting.
- note(frontend): `ForcePasswordChange.tsx` — NOT given a back link. This page is
  the mandatory gate for temp-password accounts; `ProtectedRoute` redirects back
  to it until `mustChange = false`. A back link would bypass the security gate.
  The existing "Sign out" button is the correct and intentional escape hatch.
- CI gate: 35 test files, 180 tests green; 0 lint errors; clean build — verified
  with both `.env` and `.env.local` absent.

### Added (Phase 10.6c — Root card density, sticky footer, platform name, assistant icon)

- fix(frontend): Root card density — `Card` primitive spacing tightened:
  `gap-6 → gap-3` (24px→12px between children), `py-6 → py-4` (24px→16px
  outer vertical padding). Root cause of oversized cards app-wide. All per-page
  `py-0` overrides from 10.6b remain correct and needed (list-row cards
  intentionally zero the Card outer padding so only `CardContent.p-4` controls
  spacing). Full before/after: `flex flex-col gap-6 ... py-6` →
  `flex flex-col gap-3 ... py-4`. Only the two spacing utilities changed;
  all other Card attributes, exports, and sub-components untouched.
- fix(frontend): Footer always visible — changed from `min-h-screen flex flex-col`
  (only pinned on short pages) to `fixed bottom-0 left-0 right-0 z-10
  bg-background` (always visible on both short and long pages). `pb-14` (56px)
  added to the content wrapper so the last list item is never hidden behind the
  ~50px fixed footer. `sticky bottom-0` was rejected: it only sticks when the
  element approaches the viewport bottom while scrolling, not from the top —
  on a long page the footer is not visible until you scroll to the very bottom.
- fix(frontend): SignIn title `SportSlot` → `SlotSense` (platform login brand).
  Updated `SignIn.test.tsx` and `app.render.test.tsx` to assert "SlotSense"
  (intended string change, not a test weakening).
- fix(frontend): Booking Assistant card emoji `🤖` → `<Bot>` lucide icon in
  `Facilities.tsx`, sized `size-4`, consistent with the app icon system.
- CI gate: 35 test files, 180 tests green; 0 lint errors; clean build — verified
  with both `.env` and `.env.local` absent.

### Added (Phase 10.6b — Density and layout polish)

- fix(frontend): Removed forced Card dead-space — `Card` primitive has `py-6` (48px outer
  vertical) baked in; TenantFacilities, TenantUsers, TenantList, and MyBookings cards now
  add `py-0` to neutralize it. Cards size to content; Facilities was already correct.
- fix(frontend): Mobile stacking — all list cards (TenantFacilities, TenantUsers, MyBookings)
  changed from `flex items-center justify-between` to `flex flex-col gap-3 sm:flex-row
  sm:items-center sm:justify-between`. Action buttons no longer clip off-screen on narrow
  viewports; touch targets remain ≥44px.
- fix(frontend): Footer pinned to viewport bottom — `AuthedLayout` now uses `min-h-screen
  flex flex-col` wrapper with `flex-1` content div. Footer stays at viewport bottom on short
  pages; appears below content on long pages; does not overlap or break scroll.
- fix(frontend): De-emphasized Remove/Deactivate triggers (ADR-0028 §5) — changed default
  text color from `text-destructive` (permanently red) to `text-muted-foreground`; danger
  color now appears only on hover (`hover:text-destructive hover:bg-destructive/10`).
  ConfirmDialog confirm flow unchanged; accessible names unchanged.
- note(frontend): Shared max-w container (STEP 3) — all pages already carry per-page
  `max-w-3xl`/`max-w-lg` on `<main>`. AuthedLayout cannot add max-w around Outlet without
  clipping AppHeader's full-width `border-b` (AppHeader is inside the Outlet, rendered by
  each page). No shared wrapper needed.
- note(frontend): Form input height (STEP 6) — Input primitive already uses `h-9` (36px
  standard control height). All forms are already width-capped (`max-w-md`/`max-w-lg`).
  No change required.
- CI gate: 35 test files, 180 tests green; 0 lint errors; clean build — verified with both
  `.env` and `.env.local` absent.

### Added (Phase 10.6a — SlotSense identity + footer co-branding)

- feat(frontend): Replaced all four placeholder PWA icons/favicon with the real SlotSense
  mark generated from `frontend/public/slotsense-icon-source.png` (1024×1024 PNG).
  Generation script: `frontend/scripts/gen-icons.mjs` (sharp; documents reproducible
  icon pipeline). Maskable variant composites source at 80% scale onto navy `#1a4d8f`
  canvas so the SS glyph + court-lines stay inside the safe-area circle.
- feat(frontend): Added `SlotSenseWordmark` component — flat inline SVG (navy `#1a4d8f`
  rounded square with white "SS", 18×18) + "SlotSense" text span. Crisp at 13–20px;
  no gradients; themeable via `className`; accessible visible text. 2 render tests.
- feat(frontend): Wired "powered by SlotSense" footer into app shell via `AuthedLayout`
  (React Router layout route). Footer appears on all authed routes (resident, tenant-admin,
  platform-admin); omitted on bare auth pages (SignIn, ForgotPassword, ResetPassword,
  ForcePasswordChange). Tenant header (logo + name) in AppHeader is UNCHANGED.
- CI gate: 35 test files, 180 tests green; 0 lint errors; clean build (precache 8 entries)
  — verified with both `.env` and `.env.local` absent.

### Added (Phase 10.4 — PWA manifest + icons)

- fix(frontend): Renamed PWA `name`/`short_name` from "SportSlot" → "SlotSense" in
  `vite.config.ts` manifest block; confirmed no "sportslot" string remains in
  `dist/manifest.webmanifest`.
- feat(frontend): Populated `icons: []` with three real entries (192×192, 512×512,
  maskable 512×512); all PNG files added to `frontend/public/` and emitted to
  `dist/` by Vite's static asset pipeline.
- feat(frontend): Added `favicon-32x32.png` to `frontend/public/`; wired in
  `index.html` via `<link rel="icon" type="image/png" sizes="32x32">`.
- fix(frontend): Updated `<title>` in `index.html` from "SportSlot" → "SlotSense".
- **PLACEHOLDER icons** — `pwa-192x192.png`, `pwa-512x512.png`, `pwa-maskable-512x512.png`,
  and `favicon-32x32.png` are generated navy (#1a4d8f) + white "S" PNGs; flagged for
  replacement with real brand artwork before public launch.
- **SW refresh story** (`registerType: "autoUpdate"`): new SW installs and activates
  immediately on next deploy; `skipWaiting()` + `clientsClaim()` ensure open tabs switch
  to new assets without a user prompt.
- feat(frontend): Added `workbox: { cleanupOutdatedCaches: true }` — prunes stale
  precache entries from previous deploys on SW activation; zero user-facing impact.
  Confirmed `e.cleanupOutdatedCaches()` call emitted in `dist/sw.js`.
- CI gate: 34 test files, 178 tests green; 0 lint errors; build clean — verified with
  both `.env` and `.env.local` absent.

### Added (Phase 10.3e �� Platform-admin pages; Phase 10.3 complete)

- feat(frontend): Restyled TenantList onto Card/CardContent tenant rows; real `<h1>/<h2>`;
  "+ New tenant" as `Button asChild` Link; styled loading, error, and empty ("No tenants yet.")
  states; tabular-nums for slug/status line; inline style objects removed.
- feat(frontend): Restyled CreateTenant onto labeled Input form + Button; real `<h1>`;
  token utilities; error state uses `text-destructive`; inline styles removed. No AppHeader
  (standalone form, unchanged from existing behavior).
- feat(frontend): Restyled CreateUser onto labeled Input form + Button; real `<h1>` for
  both form state and success state; token utilities throughout. Credential/temp-password
  flow PRESERVED: `CredentialDisplay` usage, `created` state shape, "Add another" button
  (→ `Button variant="outline"`), "← Back to tenants" link, and copy affordance unchanged.
  Native `<select>` kept for combobox role compatibility with all 7 existing tests.
- test(frontend): Added TenantList.test.tsx (6 tests: headings, "+ New tenant" link href,
  tenant row render, loading, error, empty state). Mocks: AppHeader, adminHooks direct —
  no importOriginal, CI-safe.
- test(frontend): Added CreateTenant.test.tsx (3 tests: heading, submit button, fallback
  error on non-ApiClientError rejection). Mocks: adminHooks, lib/api direct — CI-safe.
- No destructive one-click actions found in TenantList, CreateTenant, or CreateUser.
- **Phase 10.3 (page restyle) COMPLETE.** All pages — auth, resident, booking grid,
  tenant-admin, platform-admin — are now on the design system. 178 tests green.

### Added (Phase 10.3d — Tenant-admin pages restyle)

- feat(frontend): Restyled TenantDashboard onto Card-style Link grid; real `<h1>`;
  token utilities; inline style objects removed.
- feat(frontend): Restyled TenantFacilities onto Card/CardContent rows; real `<h1>/<h2>`;
  labeled Input/select form; Button primitives; styled loading/error/ok states;
  tabular-nums for facility times. Applied ADR-0028 §5 destructive posture: "Remove"
  is now a de-emphasized ghost trigger → ConfirmDialog confirm before deactivate fires.
- feat(frontend): Restyled TenantPolicies onto labeled Input form; real `<h1>`; Button
  submit; token utilities throughout; inline style objects removed.
- feat(frontend): Restyled TenantUsers onto Card/CardContent user rows; real `<h1>/<h2>`;
  labeled Input/select form; "Issue temp password" → Button variant="outline";
  "Deactivate" → de-emphasized ghost trigger → ConfirmDialog confirm before mutate fires
  (ADR-0028 §5); tabular-nums on bulk report counts.
- feat(frontend): Restyled TenantBranding (presentation only) onto labeled Input form;
  color-picker chrome with token classes; Button submit; token utilities. Branding
  read (useQuery/apiFetch/useEffect prefill) and write (submit handler/body construction/
  updateBranding.mutateAsync) are unchanged — ADR-0028 load-bearing logic untouched.
- test(frontend): Updated TenantFacilities.test.tsx deactivate test to click through
  ConfirmDialog (trigger → dialog confirm → mutate); imported `within`.
- test(frontend): Added TenantDashboard.test.tsx (2 tests: heading, nav links).
- test(frontend): Added TenantPolicies.test.tsx (3 tests: heading, button, pending state).
- test(frontend): Added TenantBranding.test.tsx (3 tests: heading, label, button).
  Mocks: AppHeader, AuthContext (claims=null → query disabled), tenantAdminHooks,
  lib/api — no importOriginal, CI-safe. Total: 169 tests green.

### Added (Phase 10.3c — Booking grid restyle: SlotGrid, FacilityAvailability, MyBookings)

- feat(frontend): Restyled SlotGrid.tsx — available slots use `bg-success text-success-foreground`
  token utilities; non-bookable slots use `bg-muted text-muted-foreground`; "available" label added
  to bookable slots so state is conveyed by text AND color, never color alone. Inline styles replaced
  with `cn()` + Tailwind token utilities; `min-h-[44px]` touch targets; `tabular-nums` on times;
  responsive `auto-fill minmax(96px,1fr)` grid; empty state renders "No slots available." paragraph.
  Peak token N/A — `Slot` type has no peak/premium field.
- feat(frontend): Restyled FacilityAvailability.tsx — real `<h1>` heading; labeled date `<input>`
  with token-class border/ring styling; slot-state legend (color swatch + text label for available
  and unavailable); quota advisory and feedback banners use token utilities; ConfirmDialog error
  text uses `text-destructive`. All inline `style={}` props removed.
- feat(frontend): Restyled MyBookings.tsx — booking rows use Card/CardContent primitives; Cancel
  uses `<Button variant="destructive" size="sm">`; facility name and date/time line use token
  utilities with `tabular-nums`; feedback banner uses `text-success`; all 5 existing tests green.
- test(frontend): Expanded SlotGrid.test.tsx from 1 → 6 tests: existing onPick/disabled guard,
  "available" label shown on bookable slot, reason label ("booked") shown on non-bookable slot,
  booked button `toBeDisabled()`, available button `not.toBeDisabled()`, empty slots renders
  "No slots available." message.
- test(frontend): Added FacilityAvailability.test.tsx (5 tests: Availability heading, date input,
  loading state, slot render from API, quota advisory). Mocks: `bookingHooks` (direct, no
  importOriginal) + `lib/api` — no Firebase chain loaded, CI-safe. Total: 161 tests green.

### Added (Phase 10.3b — Resident pages (Facilities, Account) + auth density)

- feat(frontend): Restyled Facilities.tsx onto Card/Button/token utilities with real <h1>
  heading, styled loading/empty/error states, tabular-nums for open/close times, and
  Button primitive for the "My bookings" nav link. Added empty-state text.
- feat(frontend): Restyled Account.tsx using AuthCard wrapper; Input/Button primitives
  with labeled fields; token utilities throughout. Placeholders preserved verbatim.
- test(frontend): Added Facilities.test.tsx (7 tests: heading, facility render, link href,
  loading, error, inactive filter, empty state). Total: 151 tests green.
- fix(frontend): Auth card density tightened — AuthCard CardContent: space-y-4 → space-y-3;
  form field spacing: space-y-3 → space-y-2. Input height unchanged (touch targets kept).
  All 19 auth page tests green after change.

### Added (Phase 10.3a — Auth flow restyle + font cleanup)

- feat(frontend): Restyled SignIn, ForgotPassword, ResetPassword, ForcePasswordChange onto
  Card/Input/Button + Tailwind token utilities via a shared AuthCard wrapper (max-w-sm,
  centered, dark-safe, responsive). All roles/labels/text/handlers preserved verbatim.
  Inline style props replaced with token utilities (text-primary, text-destructive,
  text-muted-foreground, bg-background). No raw hex values introduced.
- test(frontend): Added SignIn.test.tsx (6 tests: heading, email label, password label,
  sign-in button, forgot-password link, Google button). Total: 144 tests green.
- feat(frontend): Inter trimmed to weights 400/500, latin + latin-ext subsets only
  (was 400/500/600, all subsets). 42 font files → 8. No 600, no cyrillic/greek/vietnamese.

### Added (Phase 10.2c — Responsive shell, dark mode, Inter)

- feat(frontend): @fontsource/inter 5.2.8 self-hosted; weights 400/500/600 imported
  in main.tsx; Inter woff2 files emitted to dist/assets (no render-blocking CDN request).
- feat(frontend): Dark-mode controller (src/lib/themeMode.ts) — getInitialMode() follows
  system preference then localStorage("slotsense-theme"); applyMode() sets/removes
  documentElement.dataset.mode only; does NOT touch --color-* variables (ADR-0028 §4).
  Initialized in main.tsx before first render (no flash).
- feat(frontend): Responsive AppHeader shell — desktop: full horizontal nav; mobile (<sm):
  nav collapses behind a hamburger (Menu/X icon); opening reveals nav children + Account +
  Sign out; all touch targets >= 44px. Dark-mode toggle (Sun/Moon) reachable at all widths.
- test(frontend): 10 themeMode unit tests; 9 new AppHeader tests (toggle, mobile menu,
  dark mode × branding coexistence); 138 total tests green.
- Verified: dark mode coexists with runtime tenant branding — applyMode() never
  clobbers --color-primary overrides applied by branding.ts (ADR-0028 §4).

### Added (Phase 10.2b — Base primitives + first component restyle)

- feat(frontend): shadcn primitives installed: button, card, dialog, input, badge,
  select (class-variance-authority 0.7.1 also installed as required peer dep).
- feat(frontend): AppHeader restyled with Button primitive, lucide LogOut icon, and
  Tailwind token utilities; all roles/labels/text preserved, tests green.
- feat(frontend): ConfirmDialog restyled onto the Dialog primitive; destructive action
  posture per ADR-0028 §5 (confirm = destructive variant, cancel = outline/ghost).
  All roles/accessible names/text preserved; dedicated ConfirmDialog.test.tsx added.
- test(frontend): 8 new ConfirmDialog unit tests; total 118 tests green.
- Verified runtime theming flows to live components: --color-primary CSS variable
  channel confirmed via smoke test; utility indirection proven via build probe.

### Added (Phase 10.2a — Design-system token foundation)

- feat(frontend): Tailwind CSS v4 (@tailwindcss/vite 4.3.1), shadcn scaffolding
  (components.json, cn util in src/lib/utils.ts), and lucide-react installed.
- feat(frontend): theme.css evolved into the token layer: @import tailwindcss,
  @theme block mapping shadcn tokens onto the existing --color-* contract, neutral
  scale (slate), success/warning/ring tokens, and [data-mode="dark"] overrides
  (ADR-0028).
- feat(frontend): @/* path alias configured in tsconfig.json and vite.config.ts.
- feat(frontend): Tenant-branding runtime contract preserved: branding.ts unchanged;
  accent-color: var(--color-primary) in body ensures brand overrides flow through
  even before components migrate to Tailwind utilities.
- feat(frontend): Backward-compatibility aliases (--color-text, --color-text-muted,
  --color-danger, --spacing) retained for existing inline styles; no component
  restyled in this slice.
- test(frontend): 3 unit tests for cn() utility; total 110 tests green.

### Fixed (Slice 6.7)

- fix(frontend): MyBookings page filters to upcoming+confirmed (Phase 9
  slice 6.7). Aligns the page with the agent's list_my_bookings behavior
  (slice 6.1b). Past bookings and cancelled bookings are hidden from the
  default view. Derived `today = new Date().toISOString().slice(0,10)` and
  filter `b.status === "confirmed" && b.date >= today` replaces the
  previous `status === "confirmed"` only filter. Underlying /bookings/mine
  API is unchanged. Existing test fixture date updated from "2026-06-15"
  (past) to "2027-01-15" so existing tests pass. New test
  "filters past and cancelled bookings from display" verifies all three
  cases: past confirmed hidden, future confirmed shown, future cancelled
  hidden. 107 frontend tests, tsc clean.

### Fixed (Slice 6.6)

- fix(quota): execute-time quota check now filters by sport (cross-sport
  non-interference, Phase 9 slice 6.6).
  Root cause: create_booking_with_quota counted all confirmed bookings for
  (uid, date) regardless of sport, so a single tennis booking consumed the
  badminton quota too. Policy key is max_slots_per_user_per_sport_per_day —
  per-sport enforcement was already correct in the propose-time check
  (slice 6.4b) but broken at execute-time.
  create_booking_with_quota signature gains sport: str = "" and
  facilities: list[dict] | None = None. Inside the transaction the
  query is unchanged (uid + date + confirmed — no new Firestore index
  needed); Python-side filtering then counts only same-sport bookings by
  looking each booking's facility_id up in the passed-in fac_by_id dict.
  Unknown/missing facility_id is skipped defensively.
  create_booking in services/bookings.py: imports list_facilities, derives
  sport from the already-fetched facility, fetches facilities via
  list_facilities, and threads both into _quota_create_fn.
  test_cancelled_document_is_superseded: still passes (uses default
  sport="" so same_sport_count=0, quota not triggered by the empty iter).
  2 new hermetic tests: test_quota_cross_sport_does_not_block (tennis
  booking does not consume badminton quota) and test_quota_same_sport_raises
  (tennis booking correctly consumes tennis quota → QuotaExceededError).
  364 backend tests, 91.12% coverage.

### Fixed (Slice 6.5)

- fix(agent): correctness pass — limit fix, AM/PM guard, stateful cancel
  disambiguation (Phase 9 slice 6.5).
  6.5(a) _dispatch_readonly list_my_bookings branch no longer uses the
  LLM-supplied limit (was capped at 20). Changed to limit=100. Root cause:
  Firestore returns docs in document-ID order; with limit≤15 a user with
  15+ past bookings sees 0 future bookings after the confirmed+date≥today
  filter. Now passes 100 to surface all near-future bookings. 1 regression
  test added (verifies limit=100 kwarg and total_bookings count in turn-2).
  6.5(b) Python AM→PM guard added to _dispatch_book between the hallucination
  guard and the availability check. If hour<12 AND the datetime formed by
  combining date_str+start with the tenant timezone is already past, start is
  advanced to hour+12 (e.g. "09:00" → "21:00"). Reads tenant timezone from
  PolicyService; falls through silently on any error so availability check is
  always reached. Logged as agent_book_am_past_advanced_to_pm. 2 hermetic
  tests added (past date triggers guard; future date does not).
  6.5(c) Stateful cancel disambiguation. PendingActionStore.propose() now
  also writes a secondary pointer key
  agent_pending_latest:{tenant_id}:{uid}:{action_type} → action_id (same
  TTL). New get_latest_for_user(ctx, action_type) reads the pointer then the
  main key (read-only, does not consume). _dispatch_cancel n_can≥2 branch now
  stores a cancel_disambiguation pending action containing the candidates list
  ({id, facility_id, date, start, end} per booking). run_agent pre-Vertex
  check: if a pending cancel_disambiguation exists and the user's message
  contains exactly one candidate's date AND start as substrings, consumes the
  disambiguation action, proposes a cancel pending action for the matched
  booking, and returns a confirm prompt without calling Vertex. No match or
  zero/multiple matches falls through to normal Vertex turn. New helper
  _match_disambig_candidate implements the substring matching rule. 3 hermetic
  tests: selection routes to cancel, unrelated message falls through to Vertex,
  consumed state does not interfere. Existing two multi-candidate tests updated
  (now expect 1 propose_call for cancel_disambiguation, not 0).
  362 backend tests, 91.05% coverage.

### Fixed (Slice 6.4)

- fix(agent): error mapping + propose-time quota + cancel differentiation
  (Phase 9 slice 6.4).
  6.4(a) Booking errors in run_agent_confirm now mapped by exc.code (not
  HTTP status): SLOT_CONTENDED, BOOKING_QUOTA_EXCEEDED, ALREADY_BOOKED,
  LOCK_UNAVAILABLE, SLOT_NOT_BOOKABLE, FACILITY_NOT_FOUND, INVALID_DATE
  each produce a distinct NL message. BOOKING_QUOTA_EXCEEDED includes the
  sport name (facility looked up from params). Old status-code branching
  meant 3 different 409 codes all produced "That slot was just taken."
  6.4(b) Propose-time quota check added to _dispatch_book after the
  availability read-validate and before store.propose(). Counts the user's
  confirmed same-sport same-date bookings against
  max_slots_per_user_per_sport_per_day. Returns early with a quota message
  if at limit, preventing a proposal that would fail at execute time.
  Execute-time check in create_booking retained (defense in depth). Falls
  through silently on any policy read error so the execute-time check
  remains the safety net.
  6.4(c) _filter_cancel_candidates now returns (cancellable, too_late)
  tuple instead of a single list. _dispatch_cancel differentiates:
  (0,0) → "no bookings"; (0,≥1) → "past cancellation cutoff" message
  naming the facility and date; (1,*) → existing propose flow;
  (≥2,*) → existing disambiguation flow. Users now see precisely why
  a cancellation can't proceed instead of a misleading "no bookings" reply.
  New _booking_sport helper resolves sport for a booking via facility list.
  12 existing TestFilterCancelCandidates tests updated for tuple return;
  1 stale 422 assertion updated (SLOT_NOT_BOOKABLE message changed).
  13 new hermetic tests added. 356 backend tests, 91.68% coverage.

### Fixed (Slice 6.3)

- fix(agent+notifications): move enqueue_notification from HTTP router to
  services/bookings.py:create_booking so agent-confirmed bookings now
  produce booking-confirmation emails (regression introduced when the
  notification block was written into the router handler in Slice 3, before
  the agent path existed). Both manual (/bookings POST) and agent
  (run_agent_confirm) paths now go through the same service-layer call.
  Patch path for existing tests updated from api.v1.bookings.* to
  services.bookings.*. New hermetic test confirms source="agent" enqueues
  booking_confirmed with the correct email + params. [6.3-A]
- feat(frontend): assistant empty-state heading changed to "SlotSense";
  subtext updated to describe the assistant's scope. [6.3-B]
- feat(agent): ambiguous-time rule added to _SYSTEM_TEMPLATE — when the
  user gives a bare hour without AM/PM (e.g. "7", "8 o'clock") the model
  prefers the future-facing 24-hour interpretation relative to current local
  time. Test assertion added to test_agent_preferences.py. [6.3-C]
  344 backend tests, 106 frontend tests, tsc clean.

### Added (Slice 6)

- feat(agent+frontend): polish pass after live testing (6.1 + 6.2).
  6.1(a) 12-hour AM/PM time display in proposal cards — frontend
  formatTime12 util (lib/timeFormat.ts); ProposalCard now renders
  "9:00 AM – 10:00 AM" instead of raw HH:MM. Agent NL replies remain
  24-hour (scope choice: LLM prompt change deferred).
  6.1(b) list_my_bookings agent dispatch filters to upcoming+confirmed
  only — past bookings and cancelled bookings hidden from the LLM view.
  Underlying service (/bookings/mine route, MyBookings.tsx) unchanged.
  6.1(c) Dismissed proposal cards now hide silently — no "Proposal
  dismissed." text remains in the thread.
  6.1(d) System prompt routes 'my bookings' / 'my reservations' / 'my
  schedule' / 'what do I have' / 'what's coming up' phrasings to
  list_my_bookings. Do not refuse such questions.
  6.2 AgentRequest.recent_context optional field (backward compatible,
  defaults None) carries the previous turn for lightweight cross-turn
  context — single-turn lookback only. Backend: new _recent_context_text
  helper; {recent_context} slot in system prompt rendered conditionally.
  Frontend: useAgentSendMessage now takes {message, recent_context?};
  lastUserAndAgentTurn helper in agentSession.ts assembles context from
  the sessionStorage thread before each send. 343 backend tests, 91.31%
  coverage; 106 frontend tests. [6.1+6.2]

### Added (Slice 5b)

- feat(frontend): chat UI for the booking assistant (Phase 9 slice 5b).
  Dedicated /assistant route with structured proposal cards (Confirm/Cancel),
  sessionStorage thread persistence per-tab, 5-min pre-emptive button disable
  (timer seeded from message timestamp so expiry survives refresh), welcome
  screen + 4 suggested prompt chips on empty state, dashboard peer card on
  Facilities.tsx (above the facilities grid), PWA/mobile-aware (100dvh, 44pt
  tap targets). New files: pages/Assistant.tsx, hooks/agentHooks.ts,
  lib/agentSession.ts, components/assistant/{TypingIndicator, MessageBubble,
  MessageThread, MessageInput, ProposalCard, SuggestedPrompts}.tsx,
  styles/assistant.css (keyframes + hover pseudo-classes only; everything
  else inline with CSS vars). Uses existing apiFetch + AuthContext + React
  Query patterns; no new HTTP/auth layers. On confirm success the proposal
  card is dismissed and the agent's reply message appended. On dismiss
  (Cancel button) the card is replaced inline with "Proposal dismissed."
  Both states persist in sessionStorage. 85 tests pass, ESLint clean, tsc
  clean. [5b]
  Updated (5b.1): both onError handlers in Assistant.tsx route through
  errorMessageFor() in agentHooks.ts, which maps ApiClientError.code to
  the existing messageForCode catalog (e.g. SLOT_NOT_BOOKABLE → "That slot
  can't be booked.") and appends "ref: <8-char request_id>" for
  traceability. Non-ApiClientError throws produce a distinct "check your
  connection" message. 92 tests pass. [5b.1]

### Added (Slice 5a)

- feat(agent): AgentReply gains optional pending_action_summary field (Slice 5a).
  Structured proposal data returned alongside the NL reply on book and cancel
  propose paths. Book summary: action_type, facility_id, facility_name, sport,
  date, start, end (from validated slot). Cancel summary: action_type, booking_id,
  facility_name, sport, date, start, end (from candidate booking record). Failure
  paths (hallucination guard, unbookable, 0-candidates, multi-candidate,
  store error) return summary=None. Existing AgentReply consumers unaffected —
  field is optional (default None). Foundation for chat-UI structured proposal
  cards (Slice 5b). AgentTurn gains matching pending_action_summary field.
  339 tests, 91.38% coverage. [5a]

### Fixed (Slice 4.1)

- fix(agent): system prompt tuning for tool-routing reliability (4.V findings).
  Three new rules: (A) route 'usual/preferred/last/normal' preference questions
  explicitly to get_my_preferences — "Do not refuse such questions"; (B) for book
  requests, use ambient preferences from system prompt and call book directly —
  "Do NOT call get_my_preferences as a separate step before booking"; (C) MUST
  call the book or cancel tool — never describe the action in text (anti-narration
  guard, closes the Turn-2-tools-disabled dead-end). Prompt-only change; no code
  logic change. Multi-turn tool chaining deferred as a future option.
  Live re-validation in 4.1.V. 332 tests, 91.34% coverage. [4.1]

### Added (Slice 4)

- feat(agent): preference-aware replies and gap-filling (ADR-0021 §3 read-side).
  Closes the read-side of slice 2b's preference memory. New
  services/agent/preferences.py: get_preferences() reads
  profile.preferences.last_booked, returns empty dict on any failure (fail-open —
  preferences enrich UX, never gate access). System prompt enriched per-request:
  "Your usual bookings" section only rendered when prefs non-empty; facility names
  resolved from tenant facilities list. New GET_MY_PREFERENCES tool (5th tool,
  no args): explicit fetch for "what's my usual court?" queries; returns formatted
  map or "no remembered preferences" string. check_availability replies enriched
  at code level: after the slot grid is computed, user's usual slot status is
  appended (BOOKABLE / TAKEN(reason) / OFF-GRID-TODAY) when a preference exists
  for the queried facility's sport; sport mismatch and empty prefs → no
  enrichment line; Turn 2 framing nudges the model to mention it naturally.
  Underspecified book intents (e.g. "book tennis tomorrow") fill facility/time
  from preferences via the system prompt before hitting the existing confirm-gate.
  No confirm-gate changes; no new mutations. 331 tests, 91.34% coverage. [4]

### Added (Slice 3b)

- feat(agent): cancel via propose→confirm→execute gate (ADR-0021 §3/§4, ADR-0022
  §8). Second agent mutation. CANCEL tool (sport + optional date_hint; NO
  booking_id — hallucination structurally prevented). Deterministic Python filter
  `_filter_cancel_candidates` (status=confirmed, 7-day window, sport match,
  optional date_hint narrowing); 0/1/many branching — 0→not-found reply,
  1→pending action + confirm prompt, many→disambiguation NL list. `_parse_date_hint`
  supports YYYY-MM-DD, today/tomorrow, and weekday names. Execute path:
  cancel_booking called with stored booking_id verbatim + source="agent" →
  "agent.booking_cancelled" audit event. Cancel does NOT bypass cancel_booking's
  own ownership/buffer/status checks. 311 tests, 91.10% coverage. [3b]

### Refactored (Slice 3a)

- refactor(api): extract cancel_booking into the service layer (Phase 9 slice 3
  foundation, ADR-0021 §2); manual path behavior unchanged; source param adds
  agent audit differentiation seam (ADR-0022 §8, consistent with
  2a/create_booking): "manual"→"booking.cancelled", "agent"→"agent.booking_cancelled".
  Router thinned to a single _svc_cancel_booking call; AuditRepository +
  BookingRepository kept imported for test-patch compat. [3a]

### Added (Slice 2b)

- feat(agent): booking via propose→confirm→execute gate (ADR-0021 §4, ADR-0022
  §5/§8). First agent mutation. Structured {confirm: true, pending_action_id}
  field execute — server-enforced, not model-judged. Generic Redis
  PendingActionStore (single-use, tenant+uid scoped, 5-min TTL). BOOK tool
  (hallucination-guarded + read-validates slot is bookable before writing pending
  action). On confirm: create_booking called with stored params verbatim +
  source="agent" → "agent.booking_created" audit event. Preference memory
  partial-merge on success (best-effort). Residents-only. [2b]

### Refactored (Slice 2a)

- refactor(api): extract create_booking into the service layer (Phase 9 slice 2
  foundation, ADR-0021 §2); booking endpoint unchanged in behavior; lock + quota
  + audit semantics preserved. Router is now a thin caller + best-effort
  notification (ADR-0019). `_quota_create_fn` seam keeps existing test patches
  working without edits. [2a]

### Fixed (1b.2)

- fix(docker): set PYTHONUNBUFFERED=1 so structlog JSON logs flush to stdout and
  reach Cloud Run. 1b.1's PrintLoggerFactory was correct but Python stdout is
  block-buffered in the container by default — events sat in the buffer and were
  never scraped. One ENV line in the runtime stage; no app code change. [1b.2]

### Fixed (1b.1)

- fix(logging): structlog output now reaches stdout via PrintLoggerFactory —
  Cloud Run logs now show structured JSON lines from all service code (agent,
  auth, bookings). Previously no logger_factory was set, so structlog events
  were lost. PII redaction processors and order unchanged.
- fix(agent): system prompt now anchors current date (YYYY-MM-DD + weekday) in
  the tenant's timezone so the model can resolve relative dates ("tomorrow",
  "Saturday") before calling check_availability.
- fix(agent): list_my_bookings Turn 2 framing now pre-summarizes the tool result
  (total_bookings=N + per-booking lines) and marks it AUTHORITATIVE data, fixing
  the "wasn't able to retrieve bookings" false-failure. Diagnostic log added:
  agent_bookings_dispatched with count (no PII). [1b.1]

### Added (Slice 1b)

- feat(backend): read-only AI query agent — residents-only single-turn
  assistant (POST /api/v1/agent/query). Two tools: check_availability +
  list_my_bookings; book/cancel gated out by capability schema.
  Hallucination guard validates LLM-returned facility_id against real
  tenant list before any service call. Dual output guard: rules-based
  (email/password/uid patterns, 2 KB cap) + LLM classifier (second Flash
  call, agent_output_guard_enabled setting). Fail-closed on any Vertex or
  parse error. Uses google-genai unified SDK v2.9.0 with ADC (no API key).
  Lazy Vertex client init avoids import-time credential failures.
  14 hermetic tests — ZERO real network/Vertex calls. ADR-0021 §2 (1b).
  (review fixes: hallucination-guard test wiring; tool-schema type fidelity)

### Refactored (Slice 1a)

- refactor(api): extract get_availability and list_my_bookings into the
  service layer (Phase 9 agent foundation, ADR-0021 §2); endpoints
  unchanged in behavior. _is_cancellable moved to services/bookings.py;
  single copy shared by my_bookings and cancel_booking.

### Added (Phase 7.2.4a)

- feat(frontend): voluntary /account change-password page (no re-auth,
  ≥12 gate, stays on page on success). "Account" link in AppHeader.
- fix(frontend): ForcePasswordChange session guard — redirects to /signin
  when unauthenticated instead of failing on submit; sign-out escape hatch
  added below form.
- fix(backend): welcome-email login_url now config-driven via
  welcome_login_url setting (was hardcoded dead subdomain /login path).
- fix(frontend): admin "Reset password" button → "Issue temp password"
  to disambiguate from self-service forgot-password. ADR-0020 A2 (7.2.4a).

### Added (Phase 7.2.3)

- feat(frontend): self-service password reset pages — /forgot-password
  (enumeration-safe, uniform confirmation on success + error) and
  /reset?token=... (strips token from URL on mount, client gate ≥12
  chars, RESET_TOKEN_INVALID link-to-request). Public routes, no new
  dependencies. "Forgot password?" link on SignIn. ForcePasswordChange
  client gate bumped 8→12 for policy consistency. ADR-0020 A2 (7.2.3).

### Added (Phase 7.2.2b)

- feat(auth): self-service password reset confirm endpoint
  (/auth/forgot-password/confirm) — single-use token consume (transactional),
  policy-validated, session revocation, audit. ADR-0020 A2 (7.2.2b).

### Added (Phase 7.2.2a)

- feat(auth): self-service password reset request endpoint
  (/auth/forgot-password) — token mint, fail-closed per-email cooldown,
  branded Resend email, enumeration-safe. ADR-0020 A2 (7.2.2a).

### Added (Phase 7.2.1)

- feat(auth): shared password policy (zxcvbn + HIBP), enforced on
  /me/change-password; closed logging redaction gap (new_password,
  oobCode). ADR-0020 (7.2.1).

### Fixed (Add User field order)

- UX: reorder Add User form so Role precedes the (resident-only) Flat
  number field.

### Fixed (flat-number resident-only)

- Fix: flat_number is resident-only. API model made flat_number optional
  (was required str -> 422 when creating a tenant_admin without a flat —
  the tenant-creation 422). Frontend hides/omits the flat field unless
  role=resident. Service already enforced resident-only; now consistent
  across all three layers. Tracker: fixes the flat-field UX +
  tenant-creation 422.

### Fixed (Phase 7.x)

- Phase 7.x: forced-password gate re-prompting after a successful change.
  Root cause was NOT a query-key mismatch (`usePasswordGate.ts` and
  `ForcePasswordChange.tsx` both already used `["profile"]`) — invalidate/
  refetch defaulted to active observers; the standalone /force-password
  route has none, so the refresh was a no-op and ProtectedRoute read stale
  cached must_change_password=true on mount. Fixed by forcing type:'all'
  refetch + optimistic setQueryData before navigation. `usePasswordGate.ts`
  now exports `PASSWORD_GATE_QUERY_KEY` as the single shared key constant.
  Regression test seeds the cache with `must_change_password:true` and no
  active gate observer (mirroring the real standalone route), runs the
  change-password flow, then mounts a brand-new `ProtectedRoute` observer
  and asserts the value is correct on its very first render (no `waitFor`,
  which would mask a transient bounce back to /force-password) — confirmed
  to fail against the pre-fix code (plain `invalidateQueries`) and pass
  against the fix, per the Phase 5 false-positive lesson. Tracker: 7.x ✓.

### Added (Phase 7.1.3)

- Phase 7.1.3: wire booking-confirmed and user-welcome notification enqueues
  at their event sites; best-effort (never blocks the user action); hermetic
  tests incl. enqueue-failure isolation. `api/v1/bookings.py::create_booking`
  calls `enqueue_notification(event_type="booking_confirmed", ...)` after the
  booking is durably written (after `create_booking_with_quota` + the audit
  write, before `return doc`), resolving the booking user's email/display name
  via `UserProfileRepository(ctx, client).get(ctx.uid)` (the same pattern as
  `/users/me`) and the tenant's `display_name` via a direct tenant-doc fetch.
  `services/provisioning.py::UserProvisioningService.create_user` calls
  `enqueue_notification(event_type="user_welcome", ...)` after the existing
  create/profile/audit try-except block succeeds (deliberately outside that
  block, so an enqueue failure can never trigger the `fb_auth.delete_user`
  rollback path) — `login_url` is built from `Settings.base_domain` +
  `tenant_slug`; `temp_password` is included since it's already surfaced
  in-app via `CredentialDisplay`, the profile is created with
  `must_change_password=True` bounding its exposure window, and it's never
  logged anywhere in the enqueue/worker path. Both call sites wrap enqueue in
  a `try/except Exception` that logs a `structlog` warning and never
  re-raises — Cloud Tasks delivery failures are covered by the queue's own
  retry policy (7.1.2); this guard is only for enqueue-time failures, and the
  booking/provisioning write has already succeeded by the time it runs.
  Testability follows the codebase's existing convention for plain-function
  collaborators (matching `fb_auth.create_user`/`create_booking_with_quota`):
  `enqueue_notification` is imported directly and patched by module path in
  tests, rather than introducing a new dependency-injection wrapper. 5 new
  tests: booking-confirmed enqueue with correct `to`/params (params also fed
  through the real `render_booking_confirmed` to prove worker-side
  acceptance), booking succeeds when the enqueuer raises, enqueue skipped
  (not crashed) when no profile/email is resolvable, user-welcome enqueue
  with correct `to`/params (params fed through `render_user_welcome`), and
  provisioning succeeds when the enqueuer raises (rollback NOT triggered).
  ruff clean · bandit clean · 157 passed · coverage 92.94% (gate 90%). No
  infra/Terraform change — pure application wiring. Tracker: 7.1.3 ✓.

### Added (Phase 7.1.2)

- Phase 7.1.2: Cloud Tasks notification pipeline — queue + OIDC-authenticated
  worker endpoint + enqueue helper + invoker SA/IAM (Terraform) + resend-api-key
  secret wiring. No event triggers yet (7.1.3). `POST /internal/tasks/notify`
  (new `api/internal/` router, mounted outside `/api/v1`) verifies the Cloud
  Tasks OIDC bearer token via `google-auth`'s `id_token.verify_oauth2_token`
  (audience = worker URL, caller email pinned to `sa-tasks-invoker`); dispatches
  to the booking-confirmed/user-welcome templates and the configured
  `EmailProvider` (`ResendEmailProvider` in prod, `FakeEmailProvider` via
  `dependency_overrides` in tests); runs the sync `provider.send()` off the
  event loop via Starlette's `run_in_threadpool`. Returns 2xx on success, 503
  on `EmailSendError` (Cloud Tasks retries per the queue's `retry_config`), 422
  on unknown `event_type`/bad params (no retry), 401/403 on missing/invalid/
  wrong-SA OIDC. `notifications/tasks.py::enqueue_notification()` builds the
  Cloud Tasks HTTP task (OIDC token signed as `sa-tasks-invoker`,
  audience = worker URL); raises `TasksConfigError` loudly if queue/worker
  settings are missing rather than failing silently. Terraform
  (`terraform/cloud_tasks.tf`, Coordinator-applied): `google_cloud_tasks_queue`
  "notifications" (asia-south1, max_attempts=5, 5 dispatches/sec — Resend's
  100/day free-tier cap), new `sa-tasks-invoker` SA, `roles/run.invoker` on
  `sport-slot-api` (gcloud-deployed, not TF-managed, so bound by name/location)
  for that SA, queue-scoped `roles/cloudtasks.enqueuer` + SA-scoped
  `roles/iam.serviceAccountUser` (actAs) for `sa-cloud-run`, and
  `roles/secretmanager.secretAccessor` on the pre-existing `resend-api-key`
  secret for `sa-cloud-run`. `deploy_cloud_run.sh` now reads the service's
  existing URL before deploy (for `SPORTSLOT_WORKER_BASE_URL`) and adds
  `SPORTSLOT_TASKS_QUEUE`/`SPORTSLOT_TASKS_LOCATION`/`SPORTSLOT_TASKS_INVOKER_SA`
  env vars + `SPORTSLOT_RESEND_API_KEY=resend-api-key:latest` to `--set-secrets`.
  Narrowed `test_architecture.py`'s blanket `google.cloud` import check to
  `google.cloud.firestore` specifically (ADR-0008 Decision 3 is Firestore-only;
  the blanket match was a false positive against the new, legitimate
  `google.cloud.tasks_v2` import in `notifications/tasks.py`). 11 new tests,
  all hermetic (OIDC verification mocked, Cloud Tasks client mocked, no
  network, no real GCP). ruff clean · bandit clean · 152 passed · coverage
  92.44% (gate 90%). terraform fmt/validate clean (init-only; no plan/apply —
  Coordinator-run). Tracker: 7.1.2 ✓ (pending Coordinator `terraform apply` +
  redeploy before live).

### Added (Phase 7.1.1)

- Phase 7.1.1: EmailProvider abstraction + ResendEmailProvider + booking-
  confirmed/user-welcome templates + FakeEmailProvider + unit tests (per
  ADR-0019). `EmailProvider` is a structural Protocol (single `send()` method);
  `ResendEmailProvider` posts to the Resend HTTP API via httpx (promoted from
  dev-only to a runtime dependency), raises `EmailSendError` on non-2xx/network
  failure/missing key. Templates are pure functions returning subject+HTML+text,
  HTML-escaped via stdlib `html.escape`. `FakeEmailProvider` records sent
  messages for hermetic tests. 13 new tests, all hermetic (no network, no
  Firestore). ruff clean · bandit clean · coverage 92.05% (gate 90%).
  No Cloud Tasks / event wiring / worker endpoint yet — that's 7.1.2/7.1.3.
  Tracker: 7.1.1 ✓.

### Changed (Phase 6.3.1)

- Phase 6.3.1: remove temporary diagnostic noise from deploy_hosting_rest.sh
  (the token-length echo added during auth investigation 6.2.11–6.2.14). The
  permanent api() loud-error helper is retained. Pipeline confirmed green
  end-to-end (run 27562387259) before this cleanup. Tracker: 6.3.1 ✓.

### Added (Phase 6.1.3)

- Phase 6.1.3: grant serviceUsageConsumer to sa-firebase-admin (the impersonated
  caller for the Hosting REST deploy with X-Goog-User-Project). The principalSet
  already had this role from 6.1.1, but when auth@v3 mints a token via SA
  impersonation, the Firebase Hosting REST API enforces serviceusage.services.use
  against the impersonated SA — not the WIF principalSet. Root cause: X-Goog-User-
  Project triggers quota+billing checks on the SA's own IAM, not the WIF credential.
  Added google_project_iam_member.firebase_admin_service_usage_consumer in wif_iam.tf.
  terraform fmt OK · validate OK. Tracker: 6.1.3 ✓ (pending Coordinator apply).

### Fixed (Phase 6.2.15)

- Phase 6.2.15: translate firebase.json CLI syntax → Firebase Hosting REST API
  schema in deploy_hosting_rest.sh. firebase.json uses `source`/`destination`
  fields (CLI format) but the REST API Version.config requires `glob`/`path`.
  Sending the raw CLI fields caused 400 INVALID_ARGUMENT on version-create.
  Replaced the raw CONFIG_JSON builder with a translate() python function that
  maps source→glob, destination→path, regex→regex (passthrough), run→run
  (passthrough), and handles redirects (destination→location, type→statusCode)
  and headers (source→glob) for completeness. Verified against real firebase.json:
  output has glob/path, no source/destination keys. ShellCheck clean.
  Expected REST config: 3 Cloud Run rewrites (glob+run) + 1 SPA catch-all
  (glob:**→path:/index.html). Tracker: 6.2.15 ✓.

### Added (Phase 6.2.14)

- Phase 6.2.14: mint Firebase Hosting REST access token via sa-firebase-admin
  impersonation (token_format=access_token). Root cause confirmed: direct-WIF
  federated tokens (1484 chars) are rejected by the Firebase Hosting REST API with
  401 UNAUTHENTICATED — a real OAuth2 access token requires SA impersonation.
  Added google_service_account_iam_member.ci_token_creator_firebase in wif_iam.tf
  (principalSet→serviceAccountTokenCreator on sa-firebase-admin). Added dedicated
  auth@v3 step in deploy.yml (service_account + token_format: access_token) before
  the Hosting deploy; token passed as FIREBASE_ACCESS_TOKEN env var. REST script
  uses FIREBASE_ACCESS_TOKEN if set, else falls back to gcloud (local use).
  build/run keep direct WIF. ADR-0018 updated. terraform fmt OK · validate OK.
  ShellCheck clean · YAML valid. Tracker: 6.2.14 ✓ (pending Coordinator tf-apply).

### Fixed (Phase 6.2.13)

- Phase 6.2.13: REST Hosting deploy — revert token command to plain
  `gcloud auth print-access-token` (application-default re-exchanges the OIDC
  subject token mid-job and fails "Connection refused"; the WIF credential is
  already in the active-account store from auth@v3). Keep X-Goog-User-Project
  header (added 6.2.12). Add api() helper that prints HTTP status + response
  body on >=400 so failures are diagnosable; all JSON API calls (version-create,
  populateFiles, finalize, release) routed through it; upload calls also capture
  + print status/body on error. ShellCheck clean · bash -n clean. Tracker: 6.2.13 ✓.

### Fixed (Phase 6.2.12)

- Phase 6.2.12: REST Hosting deploy uses `gcloud auth application-default print-access-token`
  (mint token from WIF ADC, not the empty active-account store that `gcloud auth
  print-access-token` reads in CI). Added X-Goog-User-Project: sport-slot-dev header to AUTH
  array so every API call carries the quota/project context (required for ADC tokens, per
  gcloud docs; firebase-tools --debug also sends x-goog-user-project). Added token-length
  echo for debug visibility (token itself never logged). Fixes the 401 on version-create.
  ShellCheck clean · bash -n clean. Tracker: 6.2.12 ✓.

### Added (Phase 6.2.11)

- Phase 6.2.11: keyless Firebase Hosting deploy via REST API + gcloud access token.
  firebase-tools 15.x cannot consume WIF external_account ADC (confirmed via --debug:
  "No OAuth tokens found", crash on undefined.access_token). Solution: scripts/
  deploy_hosting_rest.sh drives the Firebase Hosting REST API directly with
  `gcloud auth print-access-token` (gcloud authenticates via WIF correctly — proven).
  No JSON key, no FIREBASE_TOKEN, no firebase-tools in CI. SPA rewrites + Cloud Run
  rewrites from firebase.json passed in version-create config (deep links preserved).
  Local make deploy-hosting unchanged (interactive firebase-tools login). ADR-0018
  updated with the firebase-tools WIF incompatibility finding. ShellCheck clean.
  Tracker: 6.2.11 ✓.

### Fixed (Phase 6.2.10)

- Phase 6.2.10: Firebase Hosting CI deploy via pure WIF ADC + GOOGLE_CLOUD_PROJECT.
  Official action (6.2.9) rejected — requires firebaseServiceAccount JSON key (incompatible
  with keyless WIF org policy). Reverted to firebase-tools CLI. Removed FIREBASE_TOKEN bridge
  (6.2.8). Now relies purely on GOOGLE_APPLICATION_CREDENTIALS (WIF external_account ADC, set
  by auth@v3) + GOOGLE_CLOUD_PROJECT=sport-slot-dev (lets firebase-tools resolve the project,
  which external_account files don't embed). --debug enabled until confirmed green.
  ShellCheck clean · YAML valid. Tracker: 6.2.10 ✓.

### Fixed (Phase 6.2.9)

- Phase 6.2.9: CI Firebase Hosting deploy now uses FirebaseExtended/action-hosting-deploy@v0
  (WIF/ADC), replacing the firebase-tools CLI shell invocation that failed to consume the
  WIF external-account credential after 4 attempts. The action is purpose-built for CI and
  honours GOOGLE_APPLICATION_CREDENTIALS from auth@v3; firebaseServiceAccount is empty
  (org policy forbids static JSON keys; action falls through to ADC). build-push + deploy-dev
  remain make targets (working correctly). Local make deploy-hosting unchanged.
  Install firebase-tools step removed from deploy job (no longer needed). Tracker: 6.2.9 ✓.

### Fixed (Phase 6.2.8)

- Phase 6.2.8: firebase Hosting deploy uses a gcloud-minted access token in CI —
  firebase-tools 15.x does not reliably consume the WIF external-account ADC
  (gha-creds JSON) that auth@v3 sets. gcloud authenticates correctly via WIF;
  `gcloud auth print-access-token` mints a short-lived token exported as FIREBASE_TOKEN
  for firebase-tools to consume. Keyless: no JSON service-account key, no deprecated
  login:ci token. Local deploys unchanged (interactive firebase login path). On failure
  a --debug rerun hint is printed. ShellCheck clean. Tracker: 6.2.8 ✓.

### Fixed (Phase 6.2.7)

- Phase 6.2.7: fix firebase Hosting deploy in CI — added --non-interactive so
  firebase-tools doesn't hang or emit "An unexpected error has occurred" when stdin
  is not a TTY (the root cause of the vague CI failure). --project already present;
  parametrised to ${FIREBASE_PROJECT:-sport-slot-dev} for flexibility. Added
  firebase --version echo as a debug aid before each deploy. ShellCheck clean.
  Tracker: 6.2.7 ✓.

### Fixed (Phase 6.1.2)

- Phase 6.1.2: add roles/redis.viewer to CI WIF principal (deploy reads Redis host/port
  to wire SPORTSLOT_REDIS_* env vars on Cloud Run). deploy_cloud_run.sh no longer silences
  the Redis describe error (2>/dev/null || true removed): a permission denial was being
  masked as "not found". Now runs a single describe with value(host,port), fails loudly
  with actionable message if the call fails, and derives both values from one gcloud call.
  ShellCheck clean. terraform fmt OK · validate OK. Tracker: 6.1.2 ✓ (pending Coordinator
  tf-plan + tf-apply-dev).

### Added (Phase 6.1.1)

- Phase 6.1.1: add CI IAM — serviceusage.serviceUsageConsumer + storage.admin (project)
  to the WIF CI principalSet for `gcloud builds submit`. serviceUsageConsumer resolves
  the "serviceusage.services.use permission" denied error; storage.admin resolves the
  "forbidden from accessing the bucket [sport-slot-dev-cloudbuild]" error on source
  tarball upload. Both added as google_project_iam_member in terraform/wif_iam.tf.
  Scope note: storage.admin at project level is broader than strictly necessary; a
  bucket-scoped binding on sport-slot-dev-cloudbuild is the tighter alternative —
  deferred to Phase 9 least-privilege hardening. ADR-0018 updated. Tracker: 6.1.1 ✓
  (pending Coordinator terraform apply).

### Fixed (Phase 6.2.6)

- Phase 6.2.6: gitignore gha-creds-*.json — google-github-actions/auth@v3 writes a
  credential file (gha-creds-<hash>.json) into the repo workspace root, which
  build_push.sh's git status --porcelain clean-tree check saw as an untracked file,
  causing "working tree not clean" error and aborting the deploy. Added gha-creds-*.json
  to .gitignore under the GCP/Firebase section. Tracker: 6.2.6 ✓.

### Fixed (Phase 6.2.5)

- Phase 6.2.5: bump CI Node 20 → 22 — pnpm v11 requires Node >=22.13 (uses node:sqlite
  builtin); CI pinned node-version: 20 caused "ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite".
  Changed all 3 node-version occurrences (pr-gates.yml:47, deploy.yml:40, deploy.yml:66).
  Added "engines": {"node": ">=22.13"} to frontend/package.json as single source of truth,
  mirroring the packageManager approach. Local Node v22.17.1 — no local issue.
  YAML valid; local: install OK · lint 0 errors · 43 tests passed · build OK.
  Clears Node-20 deprecation warning ahead of GitHub's Node-24 default. Tracker: 6.2.5 ✓.

### Fixed (Phase 6.2.4)

- Phase 6.2.4: fix pnpm version mismatch — CI pinned pnpm v9 but the project uses v11
  (allowBuilds syntax in pnpm-workspace.yaml, no packages field, is valid v11 and invalid
  v9). Added "packageManager": "pnpm@11.5.2" to frontend/package.json as the single source
  of truth; both workflows (pr-gates.yml, deploy.yml — 3 occurrences) now use
  pnpm/action-setup@v4 with package_json_file: frontend/package.json instead of
  hardcoded version: 9. Resolves "packages field missing or empty" in CI.
  Local: lint 0 errors · 43 tests passed · build OK. Tracker: 6.2.4 ✓.

### Fixed (Phase 6.2.2)

- Phase 6.2.2: fix non-hermetic test — test_validation_failed_includes_field_detail
  constructed a real Firestore client (failing in CI without ADC); now overrides the
  client dependency via dependency_overrides[get_firestore_client] = lambda: _prov_client()
  like all 20 sibling tests. Test is credential-free: passes with GOOGLE_APPLICATION_CREDENTIALS
  unset and GOOGLE_CLOUD_PROJECT="". Sibling scan: all 21 tests in test_tenant_config.py
  now have the override — zero remaining hermeticity risks. Tracker: 6.2.2 ✓.

### Fixed (Phase 6.2.1)

- Phase 6.2.1: Suppress 4 bandit B105 false positives (must_change_password Firestore field
  names in users.py + provisioning.py ×2, and WEAK_PASSWORD error code constant in
  error_codes.py) via per-line # nosec B105 with explanatory reason. B105 remains active
  elsewhere. CI backend gate now green: bandit 0 issues · ruff clean · 128 passed 91.56%
  coverage ≥ 90%. Tracker: 6.2.1 ✓.

### Added (Phase 6.2)

- Phase 6.2: GitHub Actions — pr-gates.yml (backend: ruff+bandit+pytest ≥90% coverage,
  frontend: lint+test+build, no GCP access on PRs by design) + deploy.yml (same gate suite
  on main for defense-in-depth, then keyless WIF auth + build/push backend via Cloud Build +
  gcloud run deploy + firebase deploy hosting on push to main). Deploy make targets
  (deploy_cloud_run.sh, deploy_hosting.sh) made CI-aware: interactive DEPLOY prompt skipped
  when $CI is set; manual experience unchanged. firebase-tools installed in deploy job
  (not pre-installed on runners, not in devDeps); uses WIF ADC — no interactive login needed.
  Coverage threshold 90% (measured 92% − 2% buffer per global rule). Tracker: 6.2 ✓
  (pipeline validated in 6.3).

### Added (Phase 6.1)

- Phase 6.1: WIF pool + provider activated as managed Terraform resources (imported from
  Phase-1 gcloud-created resources via IMPORT_6.1.md); data sources in wif.tf replaced by
  resource blocks; outputs.tf updated to reference resource addresses. Direct-WIF IAM bindings
  for CI deploy in wif_iam.tf: run.admin, artifactregistry.writer, cloudbuild.builds.editor,
  firebasehosting.admin + serviceAccountUser on sa-cloud-run (CI deploys as runtime SA) +
  serviceAccountUser on sa-cloud-build (flagged for Coordinator confirmation). ADR-0018 CI/CD
  security model: keyless direct WIF, repo+main-only attribute condition enforced at identity
  layer, Cloud Run deployed via gcloud (not Terraform) to avoid image-tag drift.
  Terraform fmt ✓ · validate ✓. Pending: Coordinator import + apply. Tracker: 6.1 ✓ (pending
  Coordinator import+apply).

### Added (Phase 5.6)

- Phase 5.6: Phase 5 retrospective (docs/retrospectives/phase-5.md — issue log, deferrals,
  validation quality note, carried-forward items). ADR-0014 email reconciled: §2 now names
  admin@sportbook.chandraailabs.com as the dev seed email (earlier drafts referenced
  "superadmin@…"). make reset-superadmin target + backend/scripts/reset_superadmin.py: dev-only
  one-command recovery for a lost superadmin password (NEWPW env var, refuses outside
  development). docs/roadmap.md created: phase status table, Phase 5 deferrals tracker,
  Phase 6–9 planned scope. PHASE 5 COMPLETE — Admin & Onboarding. Tracker: Phase 5 ✓.

### Added (Phase 5.5.2)

- Phase 5.5.2: Forced password change is now enforced globally via the route guards
  (`ProtectedRoute` + `TenantAdminRoute`), not just the Landing route — closes the bypass
  where reaching `/tenant/*`, `/bookings`, or `/facilities/*` directly (post-login nav,
  refresh, or direct URL) skipped the mandatory change entirely. New `usePasswordGate` hook
  fetches `/users/me` once (shared `["profile"]` query key, cached across all guards) and
  returns `{ mustChange, loading }`; platform admins excluded. `ForcePasswordChange`
  invalidates `["profile"]` on success before navigating to `/` to prevent a redirect loop
  from the stale cached flag. `/force-password` route remains un-gated. Landing simplified:
  `must_change_password` check removed (guard handles it before Landing renders) — only
  role-based routing remains. 43 frontend tests (+2: TenantAdminRoute password-gate tests).
  Build: 115 kB gzip (128 backend tests unchanged). Tracker: 5.5.2 ✓.

### Added (Phase 5.5.1)

- Phase 5.5.1: Fix forced-password-change routing for tenant_admin + shared `AppHeader` component.
  Bug fix: `enabled: !isAdmin && !isTenantAdmin` in Landing disabled the `/users/me` query for
  tenant_admin, causing `must_change_password` check to be skipped and routing directly to `/tenant`.
  Fixed by `enabled: !isAdmin` (runs for all non-platform-admin roles) with an `isLoading` gate
  before all redirects, ordering `must_change_password` check before the role-based redirect.
  New `AppHeader` component: logo + brand name (Link to "/") + optional children slot + user
  email·role badge + sign-out button. Adopted on all authenticated screens: Facilities, MyBookings,
  TenantDashboard, TenantFacilities, TenantBranding, TenantPolicies, TenantUsers, TenantList.
  41 frontend tests (+4: AppHeader×3, Landing regression guard×1). Build: 115 kB gzip
  (128 backend tests unchanged). Tracker: 5.5.1 ✓.

### Added (Phase 5.5b)

- Phase 5.5b: tenant user management UI (list active users, add, deactivate, reset password,
  bulk CSV import), admin-initiated password reset backend (ADR-0014 amendment — tenant-admin
  or platform-admin resets any user in their scope; returns temp_password once; sets
  must_change_password=true). Factored `CredentialDisplay` component with "Copied!" feedback
  shared by create/bulk/reset flows. Branding fix: GET `/tenants/{slug}/branding` now returns
  `brand_logo_url`; `TenantBranding` form pre-fills from current branding on mount (slug from
  JWT claim per ADR-0012 §2); logo renders in resident header via `getLastBranding()`.
  `flat_number` field hidden when role=tenant_admin on the Add User form (required only for
  resident). VALIDATION_FAILED 422 field detail (loc+msg) now surfaced in user-facing error
  messages. `ApiClientError` extended to carry the `detail` array. 37 frontend tests
  (128 backend tests, 92% coverage, 115 kB gzip). PHASE 5 FEATURE-COMPLETE. Tracker: 5.5b ✓.

### Added (Phase 5.5a)

- Phase 5.5a: tenant-admin UI — role-based landing (`TenantAdminRoute` → `/tenant`), dashboard
  with 4 nav cards, facilities management (catalog-based create/list/deactivate), branding form
  (brand name, primary/secondary hex color, logo URL), booking-policies form. `TenantAdminRoute`
  guards all `/tenant/*` routes; tenant_admin JWT claim redirects to `/tenant` at landing.
  `tenantAdminHooks.ts` wraps all tenant-config and facility API calls via TanStack Query.
  `TenantUsers` stubbed (Phase 5.5b). 7 new frontend tests (29 total). Build: 113 kB gzip.
  Tracker: 5.5a ✓.

### Added (Phase 5.4b)

- Phase 5.4b: tenant-admin config backend — PATCH `/tenant/branding` (hex color + http(s) URL
  validation, merge-into-map semantics), PATCH `/tenant/policies` (bounds: horizon≥1,
  buffer≥0, max_slots≥1, HH:MM time format), `/tenant/users` CRUD (POST/GET/DELETE) + bulk
  import POST `/tenant/users/bulk` (per-row report: created+temp_password or failed+reason,
  500-row cap). `flat_number` now optional for `tenant_admin` role (required for `resident`);
  `ProvisioningError(ApiError)` subclass separates expected from unexpected errors. Request
  validation 422 now includes a `"detail"` array with `loc` + `msg` per field. New
  `api/v1/tenant_config.py`; admin.py `deactivate_user` uses constructor-bound `caller_uid`.
  17 new tests (122 total, 91% coverage). Tenant-admin backend complete. Tracker: 5.4b ✓.

### Added (Phase 5.4a)

- Phase 5.4a: global facility catalog (seed + GET /facility-catalog), catalog-based tenant
  facility CRUD (POST/GET/PATCH/DELETE `/tenant/facilities`) replacing 3.2 free-form creation
  (ADR-0015). `seed_facility_catalog.py` seeds 7 types (badminton, tennis, swimming, gym,
  turf-football, table-tennis, basketball) and back-links legacy free-form facilities via
  sport-string migration. `POST /tenant/facilities` validates `facility_type_id` against
  catalog and copies `sport` from catalog doc. `DELETE /tenant/facilities/{id}` soft-deactivates
  (active=false). Removed free-form `POST /facilities` and `PATCH /facilities/{id}` (superseded).
  Removed orphaned `models/facility.py`. `firebase.json` firestore block added (indexes path
  wired). `make seed-facility-catalog` target added. 7 new tests (105 total, 90% coverage).
  ADR-0015 §1 amended: brand_logo_url is a URL field; Cloud Storage upload deferred to Phase 7.
  Tracker: 5.4a ✓.

### Fixed (Phase 5.3.1)

- Phase 5.3.1: fix — removed dev-tenant-slug pin from `_slug_from_host`; unrecognized
  hosts (localhost, *.web.app, *.run.app) now return None so the JWT tenant_slug claim
  is always authoritative (ADR-0012 §2 / ADR-0007). Previously `SPORTSLOT_DEV_TENANT_SLUG`
  silently overrode the JWT claim, breaking every non-default tenant in local dev.
  Removed `_DEV_HOSTS` (dependency.py) and `dev_tenant_slug` field (config.py); renamed
  `test_dev_override_allows_localhost_in_development` → `test_localhost_no_host_header_trusts_jwt`;
  added 3 regression guards (rvrg-on-localhost-allowed, demo-on-localhost-still-allowed,
  rvrg-subdomain-with-demo-claim-still-403). 102 tests, 90% coverage. Tracker: 5.3.1 ✓.

### Added (Phase 5.3)

- Phase 5.3: platform-admin UI — role-based routing (PlatformRoute guard), tenant list +
  create-tenant + create-user screens, one-time temp-password credential block with copy
  button ("shown only once" warning), forced password-change screen (ForcePasswordChange),
  admin error-catalog entries (6 new codes), Landing component with must_change_password
  gate (fetches /users/me post-login via TanStack Query; platform_admin → /admin redirect).
  7 test files, 22 tests. Build: 411 kB JS / 112 kB gzip. Tracker: 5.3 ✓.

### Fixed (Phase 5.2.1)

- Phase 5.2.1: fix — platform-admin tokens accepted on any host in DEV (ADR-0014
  route+role gating); admin-host segregation deferred to Phase 9 (charter exposure
  logged). Fixes superadmin lockout on localhost. Removed `is_admin_host` gate from
  `auth/dependency.py`; `require_platform_admin` is the sole authorization layer.
  Inverted test `test_platform_admin_on_any_host_allowed_adr0014`; added regression
  guard `test_platform_admin_on_localhost_allowed_regression_5221`. 99 tests, 90% coverage.
  Tracker: 5.2.1 ✓.

### Added (Phase 5.2)

- Phase 5.2: platform-admin backend provisioning — ADR-0017 (deletion/retention lifecycle,
  three-stage ACTIVE→INACTIVE→PURGED, user soft-delete + Firebase disable + cancel future
  bookings, self-deactivation forbidden), `require_platform_admin` dependency, 6 new error
  codes (TENANT_SLUG_TAKEN, INVALID_SLUG, USER_EMAIL_TAKEN, USER_NOT_FOUND,
  SELF_DEACTIVATION_FORBIDDEN, WEAK_PASSWORD), `UserProvisioningService` (create_user with
  tenant_slug lookup + AuditRepository + rollback guard, deactivate_user +
  _cancel_future_bookings), `PlatformRepository.create_tenant / get_tenant_by_slug /
  list_tenants` (collection_name guard removed to allow direct multi-collection access),
  `/api/v1/admin` router (POST /tenants, GET /tenants, POST /tenants/{id}/users,
  POST /tenants/{id}/users/bulk, DELETE /tenants/{id}/users/{uid}),
  POST /api/v1/users/me/change-password (clears must_change_password flag),
  seed_platform_admin.py + `make seed-platform-admin` (idempotent),
  composite Firestore index (bookings: uid+status+date for deactivation cancel-scan).
  13 new tests (98 total, 90% coverage). Tracker: 5.2 ✓.

### Added (Phase 5.1)

- Phase 5.1: ADR-0014 (admin architecture & identity — route gating, seeded superadmin,
  generate+force-change credentials), ADR-0015 (facility catalog → tenant instances),
  ADR-0016 (shared user provisioning, CSV bulk import). PHASE 5 IN PROGRESS.
  Tracker: 5.1 ✓.

### Fixed (Phase 4.6.1)

- Phase 4.6.1: fix — branding resolves on non-subdomain hosts (.web.app) via
  VITE_DEFAULT_TENANT_SLUG, and re-applies post-login from the JWT tenant_slug claim.
  Branding endpoint/data were correct; frontend slug resolution was the gap.
  Tracker: 4.6.1 ✓.

### Added (Phase 4.6)

- Phase 4.6: public per-tenant branding endpoint + CSS-variable application on app load,
  server-computed `cancellable` flag on /bookings/mine (reuses cancellation deadline logic —
  refactored into shared `_is_cancellable()` helper), eye-icon password toggle in sign-in,
  hide-cancel-when-closed (MyBookings shows "Cancellation closed" hint), Phase 4 retrospective,
  branding backfill in seed. PHASE 4 COMPLETE (custom domain deferred to Phase 7).
  Tracker: 4.6 ✓.

### Added (Phase 4.5a)

- Phase 4.5a: Firebase Hosting config (firebase.json rewrites /api/** → Cloud Run, SPA fallback),
  deploy_hosting.sh (Coordinator-run, guarded), X-Forwarded-Host-aware tenant cross-check
  (conditional host enforcement — recognized subdomains enforced, unrecognized hosts trust JWT
  claim; JWT remains authoritative per ADR-0007/ADR-0012 §2), Cloud Run direct ingress logged
  as accepted exposure in security charter (Phase 7 LB closure path documented). Tracker: 4.5a ✓.

### Added (Phase 4.4)

- Phase 4.4: my-bookings list + cancellation (dialog-level error handling, query invalidation
  reopens slots), proactive quota banner on availability page, sign-in show-password toggle.
  Booking dialog errors now surface in-dialog instead of closing dialog (fixes silent 409 UX).
  Tracker: 4.4 ✓.

### Added (Phase 4.3)

- Phase 4.3: ADR-0013 (error presentation/i18n — resolver chain, English catalog, fail-safe),
  TanStack Query booking hooks (useFacilities, useAvailability, useCreateBooking), facility list,
  availability grid with SlotGrid + IN_PROGRESS warning, booking confirm dialog with error
  catalog lookup. Tracker: 4.3 ✓.

### Added (Phase 4.2)

- Phase 4.2: Firebase Auth context (onIdTokenChanged, token-refresh-aware), tenant resolution
  (host subdomain + JWT claim cross-check), typed same-origin API client (apiFetch),
  sign-in page (email/password + Google), ProtectedRoute, Home page with mismatch warning.
  Tracker: 4.2 ✓.

### Added (Phase 4.1) — PHASE 4 IN PROGRESS

- Phase 4.1: ADR-0012 (hosting constraint findings — Firebase Hosting 20-subdomain cap, LB wildcard
  deferred to Phase 7; same-origin API rewrites; CSS-variable theming; Tailwind rejected) + Vite/TS
  strict/PWA scaffold with pnpm, TanStack Query, React Router, vitest + Testing Library. lint/test/build
  gates pass; bundle 209.50 kB / 68.33 kB gzip; PWA service worker generated.

### Fixed (Phase 3.6.1)

- 3.6.1: fix — cancelled bookings can be rebooked (status-aware supersede in transaction).

### Added (Phase 3.6) — PHASE 3 COMPLETE

- Phase 3.6: ADR-0011 synchronous Firestore audit trail, IN_PROGRESS slot marking + booking
  notice, concurrency proof script, Phase 3 retrospective. PHASE 3 COMPLETE
  (cloud redeploy pending Coordinator). Tracker: 3.6 ✓.

### Added (Phase 3.5)

- Phase 3.5: booking cancellation (self or tenant_admin, buffer-enforced on tenant clock,
  attribution fields) + GET /bookings/mine (cursor-paginated). Tracker: 3.5 ✓.

### Added (Phase 3.4)

- Phase 3.4: Memorystore Redis infra script (AUTH → Secret Manager), LockService (SET NX PX,
  owner-checked release, fail-closed), transactional booking creation (quota + deterministic-ID
  guards), Direct VPC egress wiring in deploy. Tracker: 3.4 ✓.

### Added (Phase 3.3)

- Phase 3.3: computed availability endpoint — pure-function slot matrix
  (past/booked/window/horizon), tenant-timezone rule evaluation, BookingRepository
  (read side), tenant timezone seeded.

### Added (Phase 3.2)

- Phase 3.2: PolicyService (override→default), Facility model + CRUD with require_role gate,
  seed v2 (tenant_admin user + tenant registry doc).

### Added (Phase 3.1)

- Phase 3.1: ADR-0009 (Redis slot locking), ADR-0010 (booking domain & policy resolution) accepted.

### Fixed (Phase 2.6.3)

- 2.6.3: retrospective investigation record corrected (omitted STEP 3 of 2.6.2;
  issue #11, audit-log findings).

### Fixed (Phase 2.7.1)

- Corrected fabricated documentation content (issue #10 in retrospective): charter
  had fictional run.allowedIngress override and omitted real allowedPolicyMemberDomains
  exception; retrospective omitted Cloud Run 404 investigation, protocol amendments,
  and issues #1/#6/#9; runbook omitted credential model; README omitted engineering
  method section. Root cause: session interruption + context compaction; Worker
  reconstructed instead of stopping. All five files replaced with verbatim content.

### Added (Phase 2.7) — PHASE 2 COMPLETE

- README.md rewritten: Phase 2 COMPLETE badge, Mermaid architecture diagram, ADR table
  (0001–0008), updated repo structure, security summary
- docs/retrospectives/phase-2.md: full Phase 2 retrospective (what went well, 7 issues
  log, key decisions, lessons learned, Phase 3 preview)
- docs/runbooks/local-development.md: replaced Phase 1 stub with comprehensive Phase 2
  backend runbook (GCP auth, dev server with PYTHONPATH, tests, seed, Docker, tenant
  routing, coordinator-only scripts, troubleshooting)
- docs/security/charter.md: v1.1 → v1.2; Org-Policy Exceptions section added
  (run.allowedIngress override documented with Phase 7 review date)

### Added (Phase 2.6) — Phase 2.6 COMPLETE

- Phase 2.6: Multi-stage Dockerfile (uv builder → slim non-root runtime); .dockerignore;
  guarded Coordinator scripts for AR/bucket setup (setup_build_infra.sh), Cloud Build push
  with git-SHA tags (build_push.sh), Cloud Run deploy min=0/max=2 sa-cloud-run (deploy_cloud_run.sh);
  Makefile: dev-env, run-dev, docker-build, docker-run, build-push, deploy-dev targets;
  config.py .env path anchored to backend/ (CWD-independent); .last_image_tag gitignored.

### Added (Phase 2.5) — Phase 2.5 COMPLETE

- Phase 2.5: GET /api/v1/users/me (TenantContext → UserProfileRepository → Firestore);
  slowapi in-memory rate limiting per ADR-0007 §5 — 429 in error envelope via middleware
  subclass (slowapi middleware bypasses app exception handlers); /healthz + /readyz exempt;
  guarded dev seed script (backend/scripts/seed_dev_user.py), Firebase token helper
  (scripts/get_dev_token.sh), Makefile seed-dev target, architecture gate test. 31 tests,
  coverage 89%.

### Added (Phase 2.4) — Phase 2.4 COMPLETE

- Phase 2.4: ADR-0008 (subcollection layout, permanent deny-all rules, repository contract);
  infrastructure/firestore.rules updated with ADR-0008 comment block + guarded deploy script;
  TenantRepository/PlatformRepository + UserProfile model. Coverage ≥80% (87%).

### Added (Phase 2.3) — Phase 2.3 COMPLETE

- Phase 2.3: FastAPI scaffold — app factory, request-ID middleware, error envelope + code
  registry, structlog with PII redaction, /healthz + /readyz, TenantContext auth dependency
  (ADR-0006/0007). Coverage ≥80% (93%).

### Added (Phase 2.2) — Phase 2.2 COMPLETE

- Phase 2.2: Security charter v1.1 committed to docs/security/charter.md (identity &
  credential model, ADR-0006/0007 alignment)

### Added (Phase 2.1) — Phase 2.1 COMPLETE

- ADR-0006: API Design Patterns accepted — URL path versioning (/api/v1/), UPPER_SNAKE
  error code registry, cursor-based pagination (offset prohibited), split liveness/readiness
  health probes outside versioned surface
- ADR-0007: Authentication & Authorization accepted — firebase-admin-only JWT verification
  (python-jose prohibited: CVE-2024-33663/CVE-2024-33664), custom claims as identity source of
  truth, accepted 1-hour staleness with selective revocation on SENSITIVE endpoints, no admin
  tenant bypass, phased rate limiting (slowapi → Redis → Cloud Armor)
- docs/adr/README.md: Phase 2 section added with index entries for ADR-0006 and ADR-0007

### Fixed
- verify_toolchain.sh exited with code 120 due to SIGPIPE when gcloud --version
  output was piped to `head -1`; `head` closed the pipe after line 1 and gcloud
  received SIGPIPE on subsequent writes — under `set -euo pipefail` this aborted
  the script mid-execution, skipping gcloud, Git, and gh CLI checks
- Replaced all `| head -1` patterns with `| sed -n '1p'` across Homebrew,
  Terraform, ShellCheck, gcloud, and gh CLI version checks; sed reads all input
  before producing output, eliminating SIGPIPE risk

### Added (Phase 1.4.3) — Phase 1 COMPLETE
- Makefile at repo root with 11 self-documenting commands (make help)
- scripts/install.sh — backend + frontend dependency installation
- scripts/tf-init.sh, tf-plan.sh — Terraform workflow helpers
- scripts/tf-apply-dev.sh — apply with single confirmation guardrail
- scripts/tf-destroy-dev.sh — destroy with double confirmation guardrail
- scripts/gcp-whoami.sh — show gcloud auth state + ADC status
- scripts/gcp-set-dev.sh — switch to sport-slot-dev project
- docs/adr/README.md — ADR index with status table for all 5 Phase 0 ADRs
- docs/adr/template.md — template for future ADRs
- docs/runbooks/phase-1-retrospective.md — lessons learned from Phase 1
- README.md updated: Phase 1 COMPLETE badge + Quick Start section
- Removed obsolete .gitkeep placeholders (5 files)
- All 7 new scripts ShellCheck clean

### Added (Phase 1.4.2)
- Documented existing GCP resources in Terraform (Option C — hybrid data sources + commented templates)
- terraform/apis.tf: 18 APIs (9 core + 9 operational) as locals + commented resource template
- terraform/iam.tf: 4 service accounts as data sources + commented resource templates with roles documented
- terraform/wif.tf: WIF pool + provider as data sources + commented resource/binding templates
- terraform/firestore.tf: Firestore documented via locals (no data source in provider v6) + commented resource
- terraform/outputs.tf: 12 outputs covering project, region, SA emails, WIF names, Firestore name/location
- Note: google_firestore_database data source absent from provider v6; using locals with known-stable values

### Added (Phase 1.4.1)
- terraform/ directory with module-ready flat structure (Option B+)
- terraform/backend.tf — remote state in gs://sport-slot-dev-tfstate (prefix: terraform/state)
- terraform/main.tf — Google + Google-beta providers pinned ~> 6.0
- terraform/variables.tf — input variables with validation (project_id, region, environment patterns)
- terraform/outputs.tf — basic variable pass-through outputs
- terraform/apis.tf, iam.tf, wif.tf, firestore.tf — empty placeholders for Phase 1.4.2 import
- terraform/terraform.tfvars.example — committed template for developer onboarding
- terraform/.terraform.lock.hcl — provider version pins (google + google-beta v6.50.0)
- .gitignore updated: scoped to terraform/ prefix, lock file explicitly NOT ignored

### Added (Phase 1.3.3)
- Firebase project enabled on sport-slot-dev (fixes G17 root cause from old SportBook postmortem)
- Firebase Web App "SportSlot Web (React PWA)" created (App ID: 1:707808711911:web:f16ca1570a30f4e5957e42)
- Web app config captured to infrastructure/firebase-web-config.json (local only, not committed)
- .gitignore patterns for Firebase config files (infrastructure/firebase-*.json)
- Email/Password and Google OAuth authentication providers enabled
- Firestore database created (Native Mode, asia-south1 / Mumbai)
- Deny-all security rules deployed via `firebase deploy --only firestore:rules`
- infrastructure/firestore.rules (deny-all baseline; tenant-aware rules added in Phase 2)
- infrastructure/firestore.indexes.json (empty — composite indexes added per query design in Phase 2)
- firebase.json and .firebaserc for Firebase CLI configuration
- sa-firebase-admin granted: roles/firebase.admin, roles/datastore.user, roles/iam.serviceAccountTokenCreator, roles/logging.logWriter
- sa-cloud-run granted roles/datastore.user for direct Firestore access
- sa-cloud-run can impersonate sa-firebase-admin via serviceAccountTokenCreator on SA resource
- infrastructure/iam-config.yaml: added authentication_strategy section documenting ADC pattern
- docs/runbooks/iam-setup.md: added ADC pattern explanation with code examples
- docs/runbooks/local-development.md: new runbook for developer onboarding

### Architecture Decisions Confirmed (Phase 1.3.3)
- Authentication uses Application Default Credentials (ADC) + Workload Identity Federation
- No static service account JSON keys generated (org policy iam.disableServiceAccountKeyCreation enforces this)
- Aligned with Google's "Secure by Default" policy and ADR-0004 5-layer defense-in-depth

### Added (Phase 1.3.2)
- 4 service accounts with least-privilege baseline roles:
  - sa-cloud-run (secretAccessor, logWriter, metricWriter, cloudtrace.agent)
  - sa-firebase-admin (placeholder — roles added in Phase 1.3.3)
  - sa-cloud-build (run.developer, artifactregistry.writer, logWriter + impersonation)
  - sa-monitoring (monitoring.editor, logWriter)
- Workload Identity Federation for GitHub Actions (no JSON keys)
- WIF restricted to main branch of chandranakkalakunta/sport-slot-reservation
- infrastructure/iam-config.yaml documenting IAM setup
- docs/runbooks/iam-setup.md
- .gitignore pattern for phase audit logs (scripts/phase-*.txt)

### Added (Phase 1.3.1)
- GCP project sport-slot-dev created under chandraailabs.com org
- Billing account 014A8C-586310-DE4575 linked
- 18 GCP APIs enabled (core infrastructure + operational)
- infrastructure/project-config.yaml documenting project setup
- docs/runbooks/gcp-project-setup.md

### Added
- Phase 1.2: Local toolchain installed and verified
- Python 3.12.13 via uv (alongside system 3.13)
- Project .venv created at repo root with Python 3.12
- Firebase CLI 15.19.1 reinstalled via pnpm (user-scope, ~/Library/pnpm)
- ShellCheck 0.11.0 installed via Homebrew
- Initial backend/pyproject.toml scaffolding
- Initial frontend/package.json scaffolding
- scripts/verify_toolchain.sh — all 13 checks passing
- Phase 1.1: Repository created with initial structure
- Phase 0 ADRs documented (ADR-0001 through ADR-0005)
- .gitignore covering Python, Node.js, Terraform, GCP, Firebase
- MIT License with Chandra AI Labs copyright
- README.md with project overview and architecture summary

## Phase History

### Phase 1 — Workspace Bootstrap (COMPLETE 2026-06-10)
- 1.1 GitHub + Local Workspace ✓
- 1.2 Local Toolchain (Python + Node) ✓
- 1.3 GCP Project + Firebase Initialization ✓
  - 1.3.1 GCP Project Foundation ✓
  - 1.3.2 Service Accounts + Workload Identity ✓
  - 1.3.3 Firebase + Firestore Initialization ✓
- 1.4 Terraform Foundation + Makefile + Docs ✓
  - 1.4.1 Terraform Foundation ✓
  - 1.4.2 Document Existing Resources ✓
  - 1.4.3 Makefile + Docs Finalization ✓

### Phase 2 — Backend API Foundation (COMPLETE 2026-06-12)
- 2.1 ADR-0006 + ADR-0007 (API design + auth decisions) ✓
- 2.2 Security charter v1.1 committed to docs/security/charter.md ✓
- 2.3 FastAPI scaffold + error envelope + TenantContext auth dependency ✓
- 2.4 Repository pattern + deny-all rules formalized + ADR-0008 ✓
- 2.5 /api/v1/users/me + slowapi rate limiting + dev seed ✓
- 2.6 Dockerfile + Cloud Run deploy scripts + papercut fixes ✓
- 2.7 Documentation closure: README, retrospective, runbook, charter v1.2 ✓

### Phase 3 — Booking Engine (IN PROGRESS)
- 3.1 ADR-0009 (Redis slot locking) + ADR-0010 (booking domain & policy) ✓
- 3.2 PolicyService + Facility CRUD + require_role + seed v2 ✓
- 3.3 Computed availability endpoint + BookingRepository (read side) + tenant timezone ✓

### Phase 0 — Foundation Decisions (complete)
- ADR-0001: Tech Stack & Software Versions
- ADR-0002: Database Technology Selection
- ADR-0003: Build Tooling Interface
- ADR-0004: Tenant Isolation Strategy
- ADR-0005: Cost Baseline & Budget Alerts
