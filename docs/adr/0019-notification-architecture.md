# ADR-0019: Notification & Email Architecture

**Status:** Accepted
**Date:** 2026-06-16
**Phase:** 7.1
**Relates to:** ADR-0009 (Redis), ADR-0016 (UserProvisioningService), ADR-0017 (deletion stages)

## Context

SportSlotReservation needs to send transactional email: booking confirmations, user welcome/credential delivery, and (in 7.2) password-reset links. GCP has no native "send email" service, so an external provider is required. The platform is multi-tenant, deployed on Cloud Run (`MIN_INSTANCES` can scale to zero), and authenticates to GCP keylessly via Workload Identity Federation with no JSON keys in the repo.

Two cross-cutting constraints shape this decision:

1. Email sending must not block or fail user-facing requests. A booking must succeed even if the email provider is slow or down.
2. The mechanism must be vendor-independent and survive infrastructure changes. In particular, it must not be coupled to the `chandraailabs.com` Google Workspace, whose long-term retention is uncertain.

## Decision

### 1. Provider: Resend, behind an `EmailProvider` abstraction

We will use **Resend** as the email delivery provider. Rationale:

- Permanent free tier (3,000 emails/month, 100/day) — no trial expiry, important given cost constraints. SendGrid removed its permanent free tier in 2025 (paid-only after a 60-day trial), eliminating it as a free option.
- Developer-first, clean API and current ecosystem relevance.
- Sufficient for dev/portfolio volume; the daily cap is acceptable at this scale.

The provider is accessed only through an `EmailProvider` interface (e.g. `send(to, subject, html, text, metadata) -> result`). Resend is one implementation (`ResendEmailProvider`). This makes the vendor a swappable detail: moving to Postmark (better deliverability) or Brevo (higher free cap) later is a single-class change, not a rewrite. This satisfies the vendor-independence constraint and decouples us from Workspace.

### 2. Delivery model: Asynchronous via Cloud Tasks

Notifications are enqueued, not sent inline. The request handler (e.g. create-booking) writes the domain change and enqueues a notification task; a separate worker endpoint consumes the task and calls the `EmailProvider`. We use Google Cloud Tasks as the queue.

Rationale:

- Decouples email latency/failure from user requests — a booking succeeds regardless of provider health.
- Built-in retries with backoff — Cloud Tasks retries failed deliveries automatically; no custom retry logic.
- Reusable background-job infrastructure — the same Cloud Tasks pattern serves async user provisioning (7.3) and retention purge (7.4), amortizing the investment across the phase.
- Cloud Run friendly — Cloud Tasks delivers via authenticated HTTP POST to a Cloud Run worker endpoint; works with scale-to-zero (a task wakes an instance).

### 3. Worker endpoint & authentication

A dedicated internal worker route (e.g. `POST /internal/tasks/notify`) consumes tasks. It is not publicly callable: Cloud Tasks authenticates to it using an OIDC token from a dedicated service account, and the endpoint verifies the caller. No shared secret; OIDC-verified caller identity, consistent with the keyless / least-privilege posture.

### 4. Secret handling: Resend API key in Secret Manager

Resend requires an API key — the project's first third-party API key. Handled consistently with existing secrets (e.g. Redis auth):

- Stored in Google Secret Manager (`resend-api-key`).
- Injected into Cloud Run at deploy via `--set-secrets` (read by `sa-cloud-run` via `secretmanager.secretAccessor`).
- Never committed to the repo, never a JSON file, never in CI logs.

This is a deliberate, contained exception to "no keys": third-party API keys are unavoidable for external services, so we minimize their number and manage them as runtime secrets rather than checked-in credentials. The keyless GCP posture (WIF) is unaffected.

### 5. Initial event set (extensible)

Start with two events, with a pipeline designed for easy extension:

- Booking confirmed — sent to the booking user.
- User welcome / credentials — sent on user provisioning.

Future events (booking cancelled, reminder, password reset in 7.2) plug into the same enqueue → worker → provider path.

### 6. Templating & multi-tenancy

- Templates are code-owned (typed render functions producing HTML + plain-text parts), not stored in the provider.
- Emails interpolate tenant name and basic context. Rich per-tenant branding (logo, colors, custom sender) is deferred to the branding sub-phase (which depends on the custom-domain / subdomain work in 7.5).
- Initial sender is a single verified address: `no-reply@mail.chandraailabs.com`. A verified sending subdomain (`mail.chandraailabs.com`) with SPF/DKIM/DMARC records must be configured in Resend for deliverability before live email flows.

## Consequences

**Positive**

- User requests are insulated from email provider health; bookings never fail on email.
- Cloud Tasks gives free retries/backoff and establishes reusable background-job infra for 7.3/7.4.
- Vendor is swappable; no Workspace coupling.
- Secret posture stays consistent and auditable.

**Negative / costs**

- More moving parts than synchronous sending (a queue + worker endpoint + invoker SA + IAM). Justified by robustness and reuse.
- A verified sending domain (`mail.chandraailabs.com`) + DNS records are prerequisites before real email flows.
- The Resend free-tier daily cap (100/day) is a ceiling to monitor; mitigated by the provider abstraction.
- Cloud Tasks adds minor GCP cost/quota (negligible at this volume).

## Alternatives considered

- **SendGrid** — removed its permanent free tier (2025); paid from day one. Rejected on cost.
- **Postmark** — best transactional deliverability and a natural fit for a booking platform, but no production-viable free tier ($15/mo from the start). Reconsider later via the `EmailProvider` abstraction if deliverability becomes critical.
- **Brevo** — higher free daily cap (300/day) but marketing/UI-first DX. Viable swappable fallback.
- **Gmail API via Workspace** — keyless via domain-wide delegation, but couples a core feature to the Workspace subscription (uncertain retention) and risks transactional-email deliverability flags. Rejected for coupling and deliverability.
- **Synchronous sending** — simpler, but couples request success to provider health and provides no reusable background infra. Rejected per the non-blocking constraint.

## Security notes

- Resend API key in Secret Manager only; injected via `--set-secrets`; least-privilege `secretmanager.secretAccessor` on the runtime SA.
- Worker endpoint authenticated via Cloud Tasks OIDC (SA identity), not public, not a shared secret.
- Task payloads kept minimal; no PII beyond the necessary recipient address and booking details.
- Phase 9 follow-up: review task-payload retention; consider encrypting sensitive fields if scope grows.
