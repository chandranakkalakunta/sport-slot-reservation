# ADR-0029: PWA Co-Branding Hierarchy

- **Status:** Accepted — 2026-07-03
- **Phase:** 10 (UI Redesign + PWA)
- **Supersedes:** none. **Extends:** ADR-0028 (Frontend Design System and Theming)
- **Deciders:** Coordinator (Chandra), Strategist (Claude Opus 4.8)

## Context

SlotSense is a **white-label SaaS platform**: the operator's brand identity
(Oakwood Residency, Green Park, etc.) is what residents see and interact with.
The platform vendor (SlotSense / Chandra AI Labs) is, intentionally, not the
primary identity residents form a relationship with. At the same time, SlotSense
is a portfolio product with its own brand, and complete platform-brand erasure
creates practical problems.

By Phase 10.4–10.6 the following were simultaneously true:

- **Per-tenant branding is implemented and shipped.** `branding.ts` injects the
  tenant's `brand_name`, `brand_logo_url`, `brand_primary_color`, and
  `brand_secondary_color` into the document at sign-in via CSS variable
  overrides. The `TenantBranding` admin UI lets tenant admins configure these
  directly. (ADR-0028 §4.)
- **The PWA manifest carries a fixed name.** `vite.config.ts` declares
  `name: "SlotSense"` and `short_name: "SlotSense"` in the PWA manifest
  (Phase 10.4). This name is what appears in the mobile OS install dialog,
  the home-screen icon label, and the browser's "Add to Home Screen" prompt.
  The manifest name cannot be dynamically set per tenant at install time
  because the manifest is fetched before authentication establishes the
  tenant context.
- **The footer "powered by" attribution was added in Phase 10.6a** (PR #58)
  as a fixed footer element — `"powered by SlotSense"` shown to all signed-in
  users regardless of tenant.

The decision to be made: what is the **canonical hierarchy** between tenant
brand and platform brand? Where does each appear? Which is primary? The answer
shapes every surface that touches branding downstream: email footers, push
notification sender, future marketing communications, in-app upgrade prompts.

## Decision

**Tenant brand is the primary identity in the running application. The SlotSense
platform brand appears only as a secondary, subordinate footer attribution.**

Specifically:

| Surface | What appears | Authority |
|---------|-------------|-----------|
| App header | Tenant logo (if set) + tenant `brand_name` | `branding.ts` runtime injection |
| App color scheme | Tenant `brand_primary_color` / `brand_secondary_color` | `branding.ts` CSS variable override |
| Footer (all signed-in views) | "powered by SlotSense" (fixed, small, muted) | Platform — not tenant-configurable |
| PWA manifest name | "SlotSense" (fixed at install time) | Platform — cannot be tenant-specific pre-auth |
| Home-screen icon label | "SlotSense" (derived from manifest) | Platform |
| Future: email transactional | Tenant name in subject/body; SlotSense in footer | Consistent with hierarchy |
| Future: push notifications | Tenant name in notification title; platform sender | Consistent with hierarchy |

The footer "powered by SlotSense" is the **minimum required platform attribution**
and the **maximum platform visibility** in the running app (outside the install
surface). It is deliberately secondary — small font, muted color, not in
the interaction path — because its purpose is attribution and portfolio
discoverability, not brand assertion over the tenant.

### The manifest-name tension

There is a deliberate inconsistency between the in-app experience (tenant brand)
and the install-time experience (SlotSense name on the home screen):

> A resident of Oakwood Residency sees "Oakwood Residency" in the header once
> they are signed in, but the home-screen icon they tapped to get there reads
> "SlotSense."

This is **accepted** for the following reasons:

1. **Technical constraint:** the manifest is fetched unauthenticated and must
   have a fixed name. Per-tenant manifest generation (serving a dynamic manifest
   from the backend at a per-tenant URL) is a viable but materially more complex
   approach (requires Cloud Run to serve the manifest, tenant-slug URL inference
   before auth, CORS configuration). The benefit — a home-screen label that says
   "Oakwood Residency" — is small for v1.
2. **Portfolio identity:** the app living on the home screen as "SlotSense" is
   consistent with the product having a portfolio-facing identity. If a potential
   customer sees a demo and asks "what is this?", the home-screen icon answers.
3. **Deferred upgrade path:** per-tenant manifest serving can be added in a later
   phase without changing the in-app branding hierarchy. The hierarchy decision is
   independent of the manifest-name limitation.

## Options Considered

### Option A — Platform-first (SlotSense dominant)

SlotSense brand in the app header; tenant name as a smaller sub-label or
section header; tenant logo either absent or scaled down.

**Strengths:** Stronger portfolio signal; consistent brand regardless of tenant
configuration quality.

**Weaknesses:** Inverts the product's value proposition. The reason a
residential community adopts SlotSense is so *they* run their own facility
under *their* brand — not so their residents use a SlotSense product. A
platform-first hierarchy would undermine the white-label selling point. It also
creates a visible inconsistency between the branding promise in sales/marketing
("your brand, your product") and what residents actually see.

**Rejected.**

### Option B — Co-equal (both brands in header, same visual weight)

Tenant logo and name alongside a persistent SlotSense wordmark in the header,
neither visually subordinate to the other.

**Strengths:** Compromise; both brands visible at all times.

**Weaknesses:** Header real estate is constrained on mobile (375px viewport
width). Two brands at equal weight compete visually and reduce space for
navigation. Neither brand gets a clean identity. Co-equal branding also
makes it harder to answer "whose product is this?" — which is the core
question the branding hierarchy resolves. Products with clear brand hierarchy
read more confidently.

**Rejected.**

### Option C — No platform attribution (pure white-label)

Tenant brand everywhere; no SlotSense mention anywhere in the UI. The app is
completely unidentifiable as a SlotSense product to residents.

**Strengths:** Maximum white-label fidelity; tenant identity is completely
uncontested.

**Weaknesses:** Zero portfolio discoverability. If a portfolio evaluator
installs the app on a demo tenant, there is nothing connecting the experience
to SlotSense or Chandra AI Labs. The "powered by" footer is the minimum
viable signal that this product has a named platform behind it. It also
eliminates any future in-app upgrade or referral path from existing tenants.

**Rejected.**

### Option D (chosen) — Tenant primary, SlotSense secondary footer

As described in the Decision section above.

## Consequences

### Positive

- The in-app experience is coherent: residents see one brand (their community's)
  and form a relationship with that brand, not with the platform.
- The branding promise in sales and marketing is exactly what ships. A tenant
  admin who configures Oakwood Residency colors, logo, and name sees that
  identity in the header immediately.
- "Powered by SlotSense" in the footer preserves portfolio discoverability and
  provides the attribution hook for future upgrade/referral flows without
  intruding on the primary UX.

### Negative / Risks

- The manifest-name inconsistency (SlotSense on home screen, tenant name
  in-app) is a known rough edge for v1. If a tenant complains, per-tenant
  manifest serving is the resolution — but that is a non-trivial infrastructure
  change deferred to a later phase.
- If future phases add push notifications, the correct hierarchy (tenant name
  in notification body, platform as sender identity) requires deliberate
  attention. If implemented naively, the notification might show "SlotSense"
  as the subject, breaking the tenant-primary hierarchy. This ADR explicitly
  binds future implementors.

### Forward-binding consequences

This hierarchy decision governs all surfaces not yet implemented:

| Future surface | Required behavior |
|----------------|-------------------|
| Push notifications (Phase 7/8) | Notification title/body names the tenant's facility and date; platform identifier ("SlotSense") is the sender fallback only |
| Transactional email footer | "Powered by SlotSense" mirrors the in-app footer; tenant name in subject line |
| In-app upgrade / referral prompts | May name SlotSense explicitly (the tenant is already attributed); resident-facing copy names the community first |
| Per-tenant manifest serving (future) | If implemented, short_name becomes the tenant's brand_name; platform attribution moves to the app description field |

## References

- ADR-0028 — Frontend Design System and Theming (branding token contract, `branding.ts`)
- ADR-0012 — Frontend Architecture (§4, original theming contract)
- Phase 10.6a PR #58 (`SlotSenseWordmark` component, footer co-branding)
- Phase 10.4 PR #57 (PWA manifest naming)
- `frontend/vite.config.ts` — manifest `name` and `short_name`
- `frontend/src/lib/branding.ts` — runtime tenant brand injection
- `frontend/src/components/AppHeader.tsx` — header brand rendering
