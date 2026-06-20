# ADR-0020: Self-Service Password Reset & Password Policy

- **Status:** Approved 
- **Date:** 2026-06-20
- **Deciders:** Coordinator (Chandra), Strategist
- **Phase:** 7.2
- **Relates to:** ADR-0007 (auth & authorization), ADR-0019 (notification architecture), ADR-0011 (audit logging), ADR-0016 (user provisioning), ADR-0017 (deletion/retention lifecycle)

> Reconcile section formatting against `docs/adr/template.md` before placing; content below is house-style-agnostic.

---

## Context

Residents currently have **no self-service password recovery**. The only recovery path is admin-initiated: `ProvisioningService.reset_password` (`provisioning.py:168`) sets a random `token_urlsafe(16)` temporary password, flags `must_change_password=True`, audits `user.password_reset`, and the value is emailed in plaintext (`templates.py:88` `temp_password` branch). That is operationally heavy and emails a credential in cleartext.

Existing related surfaces (verified by grep, 2026-06-20):

- `POST /me/change-password` (`users.py:34`) — authenticated self-change; validation is **`len(new_password) < 8` only**; calls `fb_auth.update_user(uid, password=...)`; clears `must_change_password`.
- `POST /tenants/{tenant_id}/users/{uid}/reset-password` (`admin.py:142`, platform_admin) and `POST /tenant/users/{uid}/reset-password` (`tenant_config.py:141`, tenant_admin) → both call `ProvisioningService.reset_password`.
- **No** `api/v1/auth.py` router exists; `src/sport_slot/auth/` holds middleware/deps only.
- Phase 7.1 shipped the Resend + Cloud Tasks notification pipeline (ADR-0019); live branded email verified from `no-reply@mail.chandraailabs.com`.
- Per-tenant subdomains (`{slug}.sportbook.chandraailabs.com`) are **Phase 7.5 — PENDING**; the live frontend host today is `sport-slot-dev.web.app`.

**Tenancy decision (input to this ADR):** the platform enforces **one email per community**. A rare dual-community resident is asked to use a separate email per community. Therefore one email = one Firebase user = one `tenant_id` custom claim. No membership/multi-tenant identity model is required, and this ADR does not introduce one.

---

## Decision

### 1. Reset flow — backend-orchestrated Firebase oobCode, delivered via Resend (Option A1)

A new router `api/v1/auth.py` exposes two **public (unauthenticated)** endpoints. Names are deliberately distinct from the existing admin "reset-password" (which means *admin sets a temp password*).

**`POST /api/v1/auth/forgot-password`** — body `{ email }`
- Always returns **`200`** with a single uniform body (see §4, enumeration protection).
- Resolve uid via Admin SDK `get_user_by_email`. If the user exists and is enabled: mint a reset link with `generate_password_reset_link(email, ActionCodeSettings(url=<config-driven continue URL>, handle_code_in_app=True))`, extract the `oobCode`, and enqueue a Cloud Task → Resend branded email (branding resolved from the user's `tenant_id` claim, §3).
- Rate-limited per-IP and per-email (§4).

**`POST /api/v1/auth/forgot-password/confirm`** — body `{ oobCode, new_password }`
- Validate `new_password` against the shared policy validator (§2) — **server-side authority, runs before any commit.**
- Commit via Identity Toolkit REST `accounts:resetPassword` (`oobCode` + `new_password`). The oobCode is the proof of email ownership and Firebase owns its single-use + expiry lifecycle.
- On success: clear `must_change_password`; `auth.revoke_refresh_tokens(uid)`; audit `auth.password_reset_completed`; enqueue a "password changed" confirmation email.

Rationale for A1 over alternatives: see Alternatives. The new password transits the FastAPI backend over TLS only — never logged, never stored, handed straight to Firebase.

### 2. Password policy — zxcvbn + HIBP, in one shared validator

New module `sport_slot/auth/password_policy.py`, the single source of truth:

- **Length:** min **12**, max **≥64**; all Unicode permitted; **no forced composition rules** (per NIST SP 800-63B — composition rules lower real-world entropy).
- **Strength:** `zxcvbn` score **≥ 3** required. Offline, deterministic, ships its own dictionaries; the Python port is the server authority.
- **Breach check:** HIBP Pwned Passwords **k-anonymity** — SHA-1, send only the 5-char hex prefix, request header `Add-Padding: true`, **2s timeout**. On timeout/error, **fail-open to zxcvbn-only** and log the degrade (see Security note on the fail-closed tension).
- **Client (UX only):** JS `zxcvbn` live strength meter + length check for instant feedback. The **blocklist/HIBP check stays server-side only**. A contract test keeps the length rule in parity across client/server.
- **Wiring:** the validator is enforced by **both** the new `/auth/forgot-password/confirm` endpoint **and** the existing `/me/change-password` (replacing the `len < 8` check). Admin/machine-generated temp passwords (`token_urlsafe`) are **exempt** — high-entropy, not user-chosen.

### 3. Branding & routing — by `tenant_id` claim, host config-driven

Email branding and the continue-URL are resolved from the user's `tenant_id` claim (read server-side after `get_user_by_email`), **not** from the request subdomain — correct even if the user hits the wrong host, and invisible behind the uniform `200`. The continue-URL **host** is configuration-driven: DEV = `sport-slot-dev.web.app/reset`; Phase 7.5 switches it to per-tenant subdomains **without a code change**. The continue host must be in Firebase Auth authorized domains.

### 4. Enumeration protection

- **Uniform `200`** on `/forgot-password` regardless of existence/enabled state — no branch reveals account existence.
- **Rate limiting** in Memorystore Redis: per-IP and a per-email cooldown (e.g. one mail / address / 15 min), which also closes the "send as oracle" vector.
- **Timing:** the exists path does more work than the not-found early return — a residual side channel. For this threat model the residual risk is **accepted and documented** rather than constant-time-engineered.

### 5. Session safety

`auth.revoke_refresh_tokens(uid)` on successful reset (kills any attacker session). Verify `/me/change-password` does the same; add if missing.

### 6. Audit

Distinct events from the admin path: `auth.password_reset_requested` and `auth.password_reset_completed` (no PII beyond what ADR-0011 already permits), separate from admin-initiated `user.password_reset`.

---

## Consequences

**Positive**
- Real self-service recovery; password never appears in an email (link-based, single-use, expiring).
- Consistent branded delivery via the existing 7.1 Resend pipeline.
- One strong policy unified across both user-facing password-set paths.
- **No new billable resources** — reuses Resend, Cloud Tasks, Cloud Run, Firestore, Redis; HIBP is free; zxcvbn is a code dependency. Marginal cost ≈ ₹0.

**Trade-offs / negative**
- New dependencies: `zxcvbn` (Python + JS) and an outbound HIBP HTTPS call on the confirm path.
- `/me/change-password` tightens from `len ≥ 8` to `len ≥ 12` + zxcvbn ≥ 3 (intended; affects only future changes, not existing stored passwords).
- The confirm path adds an Identity Toolkit REST dependency (`accounts:resetPassword`) needing the Firebase **Web API key** — public, not a secret. Verify any Firebase project-level password policy is ≤ ours so it can't reject first.

**Follow-ups (new Open Known Issues)**
1. Migrate admin/tenant-initiated reset from plaintext-temp-password-by-email to the oobCode link flow (`templates.py:88` / `provisioning.py:168`). Security smell; separate PR.
2. Verify `REDACTED_KEYS` (`logging.py:7`) covers `new_password` and `oobCode` — the set appears exact-match, so these may slip through request-body logging today. Make redaction substring-based or add the keys. Must-fix within 7.2.

---

## Alternatives considered

- **Option A — Firebase-native client flow** (`sendPasswordResetEmail` / `confirmPasswordReset`): rejected. Bypasses the Resend verified domain and per-tenant branding, and the client-direct reset cannot enforce the server-authoritative policy/blocklist.
- **Option A2 — own reset token + Admin SDK `update_user`**: rejected for 7.2. Sound, but hand-rolls a security-critical token system; Firebase's oobCode lifecycle is already hardened (§4.8 spirit).
- **zxcvbn-only / traditional composition rules**: zxcvbn-only is defensible but lacks breach-corpus coverage; composition rules rejected per NIST 800-63B.
- **GCIP multi-tenancy for shared email**: rejected — heavyweight identity-layer change; the one-email-per-community policy makes it unnecessary.

---

## Security charter alignment

- **Secure by Default** — uniform `200`, fail-closed verification on the OIDC/worker path is unchanged.
- **Privacy by Design** — HIBP k-anonymity (password never leaves the server); no PII in audit beyond ADR-0011.
- **Fail Closed — documented exception:** HIBP fails **open**, deliberately. The *gate never fully opens*: `zxcvbn ≥ 3` and the length rule always run and always close. HIBP is an additive check whose unavailability degrades to zxcvbn-only rather than self-inflicting a denial of all password resets. This is a conscious availability-vs-strictness trade, recorded here so it is not mistaken for an oversight.
