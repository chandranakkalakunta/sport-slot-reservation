# Security Charter — SportSlot Reservation

**Version:** 1.1 | **Date:** 2026-06-11 | **Author:** Chandra Nakkalakunta

## Principles

1. **Defense-in-Depth** — No single control trusted alone. Tenant isolation has 5 layers (ADR-0004). Auth checks both JWT and URL.
2. **Least Privilege** — 4 separate service accounts, each scoped to its function. Permissions added per phase, never "just in case."
3. **Secure by Default** — Firestore starts deny-all. Endpoints require auth by default. Org policy blocks JSON key creation.
4. **Zero Static Credentials** — No JSON keys anywhere. ADC for local dev, WIF for CI/CD, attached SA for Cloud Run.
5. **Privacy by Design** — No PII in logs. SHA-256 hashed IDs in analytics. Per-country data residency. DPDP Act compliant.
6. **Fail Closed** — Redis down → bookings pause (not bypass). Auth fails → 401 (not anonymous access).
7. **Verify, Don't Trust** — Every phase independently validated. JWT verified every request. CI gates block unverified deploys.

When principles conflict: Privacy > Fail Closed > Defense-in-Depth > Zero Credentials > Least Privilege > Secure by Default > Verify.

## Identity & Credential Model

- **admin@chandraailabs.com** — sole human cloud-management identity (gcloud, GCP Console, org administration). MFA hardening in Phase 8.
- **chandra.n@chandraailabs.com** — email and git identity (commits, correspondence). No cloud credentials.
- **Application credentials** — never a human identity. Local development uses ADC via service account impersonation (sa-firebase-admin); CI/CD uses WIF (sa-cloud-build); runtime uses the attached service account (sa-cloud-run). A development server never holds org-admin powers.

## Threat Model

**In scope (Tier 1+2):** Curious residents manipulating URLs, disgruntled users hoarding slots, tenant admins trying cross-tenant access, credential stuffing, API scraping, OWASP Top 10, compromised dependencies, DDoS during peak booking.

**Noted but not exhaustively defended (Tier 3):** Organized cybercrime, supply chain attacks (mitigated by scanning + Binary Auth).

**Out of scope (Tier 4):** Nation-state / APT. SportSlot is residential community SaaS, not critical infrastructure.

**Acceptable risks:** Google-managed encryption until CMEK in Phase 8. No VPC-SC in DEV. No MFA for residents in v1 (required for admins in Phase 8). No dedicated SOC (alerts + runbooks are proportionate). Up-to-1-hour stale JWT custom claims on non-sensitive endpoints (ADR-0007, Decision 3).

## Security Controls by Phase

### Already Done (Phase 1)
- Zero JSON keys (org policy enforced)
- 4 least-privilege service accounts
- Workload Identity Federation (main branch only)
- Firebase Auth (Email/Password + Google OAuth)
- Firestore deny-all security rules
- ADC authentication pattern

### Phase 2 — Backend Foundation
- Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- CORS strict policy (subdomain-aware)
- Rate limiting (per-user, per-IP, per-tenant)
- JWT validation middleware with tenant cross-check
- PII redaction in logs (no emails, no JWT contents)
- Request ID on every response for tracing
- Pydantic input validation on all endpoints
- Repository pattern enforcing tenant_id (ADR-0004 Layer 2)
- Firestore Security Rules with tenant_id enforcement (ADR-0004 Layer 1)

### Phase 3 — Booking Engine
- Per-user/household booking quotas (anti-hoarding)
- Redis distributed lock (anti-double-booking, ADR-0002)
- Booking cancellation rate limiting
- Audit logging for all booking mutations

### Phase 5 — CI/CD
- Binary Authorization (deploy-time image verification)
- KMS signing in Cloud Build pipeline
- Bandit SAST for Python
- pip-audit for Python CVE scanning
- pnpm audit for Node CVE scanning
- Container vulnerability scanning (gate before deploy)
- Secret scanning (Gitleaks/TruffleHog)
- All scans must PASS before deployment proceeds

### Phase 7 — Performance
- Cloud Armor Standard (DDoS protection)
- WAF rules (OWASP pre-configured rules)
- Geographic restrictions (India-only for India deployment)
- Edge rate limiting

### Phase 8 — Production Readiness
- CMEK for Firestore, Secret Manager, Cloud Storage (Cloud KMS, RSA-4096)
- VPC for Cloud Run services + Cloud NAT
- MFA required for tenant_admin and platform_admin roles
- Penetration testing
- Incident response runbook
- DPDP Act compliance formalization
- Delete protection enabled on production Firestore
- Point-in-time recovery enabled

## DPDP Act Compliance

**Data we collect:** Name, email, phone, flat number, booking history.

**What we commit to:**
- Data stored in India (asia-south1) for Indian residents
- No PII in analytics — SHA-256 hashed identifiers only
- Right to deletion — resident can request account + data deletion
- Right to export — resident can download their data
- Consent at signup — clear terms before account creation
- Breach notification — within 72 hours per DPDP requirements
- No data sold or shared with third parties

## Incident Response

**Severity levels:**
- **SEV-1:** Cross-tenant data leak, credential compromise, data breach → Respond within 1 hour
- **SEV-2:** Single-tenant disruption, auth system failure → Respond within 4 hours
- **SEV-3:** Rate limiting triggered, suspicious activity detected → Respond within 24 hours
- **SEV-4:** Non-critical security finding, dependency CVE → Respond within 1 week

**Response process:** Detect → Contain → Investigate → Remediate → Document → Review.

**Communication:** SEV-1/2 notify affected tenants. SEV-1 triggers DPDP breach notification if PII involved.

## Review Schedule

- **Quarterly:** Review charter for currency
- **After incidents:** Update based on lessons learned
- **Before major releases:** Verify new features satisfy principles
- **When compliance requirements change:** Update DPDP section

## Related Documents

- ADR-0004: Tenant Isolation Strategy (5-layer defense-in-depth)
- ADR-0002: Database Technology (distributed locks, per-country deployment)
- ADR-0005: Cost Baseline (budget for security infrastructure)
- ADR-0006: API Design Patterns (error envelope, request ID tracing)
- ADR-0007: Authentication & Authorization (JWT verification, claims staleness, admin isolation, rate limiting)
- Phase-specific ADRs will reference this charter

## Changelog

- **1.1 (2026-06-11):** Added Identity & Credential Model section; recorded accepted claims-staleness risk; added ADR-0006/0007 references.
- **1.0 (2026-06-10):** Initial charter.
