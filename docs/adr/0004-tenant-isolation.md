# ADR-0004: Tenant Isolation Strategy

## Status

Accepted — 2026-06-09

## Context

SportBook is a multi-tenant SaaS platform where multiple residential communities share the same infrastructure but must have their data completely isolated from each other. Tenant isolation is the foundational security guarantee of any multi-tenant system — a single failure here can leak one tenant's data to another, destroying customer trust and potentially violating data protection regulations.

This ADR makes two related decisions:

1. **Data Isolation Strategy:** How data is separated between tenants
2. **Tenant Identification Strategy:** How the system identifies which tenant a request belongs to

These are interconnected because the identification mechanism feeds into the isolation enforcement.

### Requirements

1. **Strong isolation guarantee:** No tenant can ever access another tenant's data
2. **Defense-in-depth:** No single point of failure for isolation
3. **Operationally simple:** Manageable at scale (hundreds of tenants per country)
4. **Cost effective:** Cannot multiply infrastructure costs per tenant
5. **Tenant onboarding simple:** No DNS or technical setup required from tenants
6. **Branding support:** Each tenant should feel they have their own dedicated space
7. **Compliance-ready:** Supports DPDP Act and other data protection regulations
8. **Foolproof enforcement:** Automated checks must prevent vulnerable code from deploying

### What This ADR Does NOT Cover

- Per-country deployment architecture (decided in ADR-0002)
- Custom domain support (explicitly NOT supported in Phase 1)
- Identity provider selection (Firebase Auth — decided in ADR-0001)

## Options Considered — Data Isolation

### Option A — Logical Isolation (Single Database, tenant_id Field)

All tenants share a single Firestore database. Every document includes a `tenant_id` field. The application is responsible for filtering by `tenant_id` on every query.

**Architecture:**

```
ONE Firestore database (per country)
Every document includes: tenant_id field
Application queries: WHERE tenant_id = current_tenant
```

**Strengths:**
- Lowest cost — single database for all tenants
- Operationally simple — one database to manage
- Scales effortlessly within Firestore limits
- Standard pattern used by most multi-tenant SaaS
- Easy backup, restore, and disaster recovery
- Cross-tenant platform analytics straightforward
- What Firestore makes natural

**Weaknesses:**
- Single missed filter in code = potential data leak
- Every developer must remember tenant_id discipline
- Noisy neighbor risk (one tenant's load affects others)
- Requires strong enforcement mechanisms

### Option B — Physical Isolation (Database Per Tenant)

Each tenant has its own dedicated Firestore database, with a master "platform" database routing requests.

**Architecture:**

```
Master database: routes tenant slug → tenant database name
Per-tenant databases: sportbook-sobha-001, sportbook-prestige-001, ...
Application connects to correct database per request
```

**Strengths:**
- Strongest possible isolation guarantee
- One tenant's bug or load cannot affect another
- Per-tenant backup and restore trivial
- Easier compliance audits per tenant
- Per-tenant cost visibility

**Weaknesses:**
- Firestore allows ~100 named databases per project — caps growth
- 200 tenants would exceed Firestore limits without project-per-tenant
- Project-per-tenant would multiply GCP project quota usage
- Cross-tenant analytics requires ETL or federation
- Master database becomes a single point of failure
- Operational complexity multiplies with tenant count
- Per-tenant cost increases
- Typical for healthcare (HIPAA), not residential community SaaS

### Option C — Hybrid (Collection-per-Tenant Within Single Database)

Single Firestore database, but each tenant gets dedicated collections prefixed with their tenant ID.

**Architecture:**

```
Collections:
  sobha_001_bookings, sobha_001_users, sobha_001_facilities
  prestige_001_bookings, prestige_001_users, prestige_001_facilities
```

**Strengths:**
- Better isolation than logical (impossible to query wrong tenant by mistake)
- Single database (cheaper than physical)
- Per-tenant Firestore Security Rules possible

**Weaknesses:**
- Firestore has soft limit on number of collections
- Cross-tenant platform queries harder
- More complex query construction in code
- Composite indexes must be created per tenant — risks hitting 200 index limit
- Non-standard pattern, harder to debug
- No meaningful security benefit over logical isolation with proper guards

## Decision — Data Isolation

**Logical Isolation (Option A) with Strong Defense-in-Depth**

A single Firestore database per country, with `tenant_id` field on every document. Enforcement is achieved through five overlapping layers of defense, ensuring no single failure can result in data leakage.

## Defense-in-Depth — The Five Layers

This is the critical design insight. We do not rely on application code to remember `tenant_id`. Instead, we engineer multiple overlapping defenses such that data leakage requires ALL layers to fail simultaneously.

### Layer 1 — Firestore Security Rules (Database-Level Guard)

Firestore Security Rules execute on Google's servers and validate every read and write against the authenticated user's token claims. They cannot be bypassed by application code, by direct database access, or by any client.

```
match /databases/{database}/documents {
  match /bookings/{bookingId} {
    allow read: if request.auth.token.tenant_id 
                == resource.data.tenant_id;
    
    allow create: if request.auth.token.tenant_id 
                  == request.resource.data.tenant_id;
    
    allow update, delete: if request.auth.token.tenant_id 
                          == resource.data.tenant_id
                          && request.auth.token.role 
                             in ['tenant_admin', 'platform_admin'];
  }
  
  match /users/{userId} {
    allow read, write: if request.auth.token.tenant_id 
                       == resource.data.tenant_id;
  }
  
  // ... applied to all collections
}
```

This is the foundation. Even if the application has a bug, Firestore itself refuses cross-tenant operations.

### Layer 2 — Repository Pattern (Code-Level Enforcement)

The application uses a repository pattern that makes it physically impossible to query without tenant_id. Repositories require a `TenantContext` in their constructor, and tenant_id is automatically applied to all queries.

```
class TenantContext:
    tenant_id: str
    user_id: str
    role: str

class BookingRepository:
    def __init__(self, ctx: TenantContext):
        # Constructor REQUIRES TenantContext
        self.tenant_id = ctx.tenant_id
    
    def get_bookings(self, user_id: str):
        # Filter ALWAYS applied
        return db.collection('bookings') \
                 .where('tenant_id', '==', self.tenant_id) \
                 .where('user_id', '==', user_id) \
                 .get()

# Usage in endpoint:
def my_endpoint(ctx: TenantContext = Depends(get_tenant_context)):
    repo = BookingRepository(ctx)  # tenant_id baked in
    return repo.get_bookings(user_id)
```

Developers cannot create a repository without a valid TenantContext. The type system (Python type hints + mypy) enforces this at compile time.

### Layer 3 — Authentication Middleware (Request-Level Extraction)

FastAPI middleware extracts and validates tenant context from every authenticated request:

```
async def tenant_middleware(request, call_next):
    # 1. Extract and verify Firebase JWT
    jwt_token = request.headers['Authorization']
    payload = firebase.verify_token(jwt_token)
    
    # 2. Extract subdomain from URL
    host = request.headers['Host']
    subdomain = host.split('.')[0]
    
    # 3. CRITICAL: Verify JWT tenant matches URL subdomain
    if payload['tenant_slug'] != subdomain:
        raise HTTPException(403, "Tenant mismatch")
    
    # 4. Construct TenantContext for downstream use
    request.state.tenant_ctx = TenantContext(
        tenant_id=payload['tenant_id'],
        user_id=payload['sub'],
        role=payload['role']
    )
    
    return await call_next(request)
```

This middleware:

- Validates the JWT signature against Firebase's keys (cannot be forged)
- Verifies the URL subdomain matches the JWT's tenant — preventing URL manipulation attacks
- Constructs an authoritative TenantContext that downstream code uses

### Layer 4 — Automated Tests (Verification)

The repository pattern compliance is verified by automated tests that explicitly attempt cross-tenant access and verify it is blocked:

```
def test_cross_tenant_access_blocked():
    # Create booking in tenant A
    ctx_a = TenantContext(tenant_id='tenant-a', user_id='user-1', role='resident')
    repo_a = BookingRepository(ctx_a)
    booking = repo_a.create_booking({...})
    
    # Try to read from tenant B's perspective
    ctx_b = TenantContext(tenant_id='tenant-b', user_id='user-2', role='resident')
    repo_b = BookingRepository(ctx_b)
    
    result = repo_b.get_booking(booking.id)
    
    # MUST be None — cross-tenant access blocked
    assert result is None
```

Similar tests exist for every collection and operation. The CI pipeline runs these tests on every commit. Any code that breaks isolation immediately fails CI.

### Layer 5 — CI/CD Deployment Gates

The CI/CD pipeline includes automated checks that prevent vulnerable code from reaching production:

**Static Code Analysis:**
- Custom Ruff rule searches for raw Firestore queries outside repository classes
- Detection of `db.collection(...).where(...)` patterns in business logic
- Fails CI on any violation

**Firestore Security Rules Tests:**
- Firebase emulator runs security rules against simulated multi-tenant data
- Tests verify each rule blocks cross-tenant access
- Fails CI if any rule is missing or incorrect

**Integration Tests:**
- Spin up Firestore emulator with two tenants of data
- Run full request flows for both tenants
- Verify zero cross-tenant data leakage in API responses

**SAST Scanning:**
- Bandit scans for security anti-patterns
- Fails on direct database client usage in business logic

**Coverage Requirements:**
- All repository methods must have isolation tests
- Coverage threshold prevents untested code from deploying

If ANY of these checks fail, the deployment is blocked. The code cannot reach production until isolation is verified.

### Why Five Layers — The Math

For a data leak to occur, ALL FIVE layers must fail simultaneously:

| Failure Mode | Layer That Catches It |
|---|---|
| Developer forgets tenant_id in query | Layer 2 (repository requires it) + Layer 5 (static analysis) |
| Repository pattern bypassed | Layer 1 (security rules block at DB level) |
| Compromised application code | Layer 1 (security rules independent of app) |
| JWT manipulation by attacker | Layer 3 (signature verification) |
| Subdomain mismatch attack | Layer 3 (URL vs JWT cross-check) |
| Bug in security rules | Layer 4 (tests catch it) + Layer 5 (CI blocks deploy) |
| Direct database client usage | Layer 5 (static analysis blocks) |

The probability of all five layers failing simultaneously is vanishingly small. This is the engineering definition of "as safe as multi-tenant SaaS gets."

## Options Considered — Tenant Identification

### Option A — Subdomain ({tenant}.sportbook.chandraailabs.com)

**Strengths:**
- Each tenant feels they have their own dedicated site
- Clear visual identification of which tenant is active
- Natural per-tenant branding (logo, colors)
- Cookie isolation by subdomain provides additional defense
- Industry standard for SaaS (Slack: acme.slack.com)
- Bookmarking works naturally
- Future-proofing for advanced routing scenarios

**Weaknesses:**
- Requires wildcard DNS configuration (one-time setup)
- Requires wildcard SSL certificate (auto-provisioned by Google)
- Application must extract tenant from Host header

### Option B — URL Path (sportbook.chandraailabs.com/{tenant})

**Strengths:**
- Simpler DNS (no wildcards)
- Single domain SSL certificate
- Faster initial setup

**Weaknesses:**
- Tenant identification less obvious to users
- Cookies shared across tenants (less isolation)
- Login redirects more complex
- Less professional feel for white-label tenants
- Branding switch jarring (same URL, different appearance)
- Harder to migrate to subdomains later

### Option C — Custom Domain (sobha-sports.community → SportBook)

**Strengths:**
- Tenant's complete white-label experience
- Strongest tenant identity

**Weaknesses:**
- Requires DNS configuration FROM TENANT
- Per-tenant SSL certificate provisioning
- Each tenant must own a domain
- Complex support burden when tenant DNS fails

### Option D — JWT Claim Only (No URL Indication)

**Strengths:**
- Simplest URL structure

**Weaknesses:**
- Users cannot bookmark tenant-specific pages
- Tenant identity invisible to user
- Branding switch jarring (same URL, different look)
- Login redirect logic complex
- Cookie sharing across tenants

## Decision — Tenant Identification

**Subdomain (Option A) — Zero DNS Requirements on Tenants**

Each tenant receives a subdomain under our parent domain:

```
{tenant-slug}.sportbook.chandraailabs.com
```

Examples:
- `sobha-dream-acres.sportbook.chandraailabs.com`
- `prestige-lakeside.sportbook.chandraailabs.com`
- `purva-the-waves.sportbook.chandraailabs.com`

Custom domains (Option C) are **explicitly not supported** in Phase 1 or beyond. The pure wildcard subdomain approach satisfies all requirements without imposing DNS burden on tenants.

## How Wildcard DNS Works — Implementation Details

The key insight that makes this approach work is wildcard DNS. ONE DNS configuration handles ALL current and future tenants.

### One-Time Setup (Phase 1)

This setup happens once and never changes:

```
1. Namecheap (or our DNS provider):
   Add wildcard CNAME record:
     Type: CNAME
     Host: *.sportbook
     Value: ghs.googlehosted.com
     TTL: Automatic
   
   This single entry covers:
     *.sportbook.chandraailabs.com → ALL subdomains

2. Cloud Run domain mapping:
   gcloud beta run domain-mappings create \
     --service=sportbook-api \
     --domain="*.sportbook.chandraailabs.com" \
     --region=asia-south1
   
   Cloud Run routes all subdomain traffic
   to our application service.

3. Wildcard SSL certificate:
   Google Cloud auto-provisions:
     *.sportbook.chandraailabs.com
   
   ONE certificate covers ALL tenants.
   Auto-renews. No per-tenant management.
```

### Per-Tenant Onboarding (Repeated for Each New Tenant)

After the one-time setup, adding new tenants requires ZERO DNS or infrastructure changes:

```
1. Platform admin opens admin panel
2. Creates new tenant:
   - Name: "Sobha Dream Acres"
   - Slug: "sobha-dream-acres" (assigned by admin)
   - Contact email, billing details, etc.

3. System creates tenant document in Firestore

4. Tenant immediately accessible at:
   sobha-dream-acres.sportbook.chandraailabs.com
   
   - DNS already configured (wildcard)
   - SSL already provisioned (wildcard)
   - Cloud Run already routing (wildcard mapping)
   - Application extracts "sobha-dream-acres" from Host header
   - Application looks up tenant_id from slug
   - Branding applied based on tenant config

5. Tenant admin can log in immediately.
   No DNS configuration required from them.
   No certificates required from them.
   No technical knowledge required.
```

### Visual Architecture

```
                User browser request
        sobha-dream-acres.sportbook.chandraailabs.com
                          │
                          ▼
                    DNS resolution
                  *.sportbook → ghs.googlehosted.com
                          │
                          ▼
                  Cloud Run service
              (single deployment serves all tenants)
                          │
                          ▼
              FastAPI tenant middleware:
                Extract subdomain → "sobha-dream-acres"
                Look up tenant_id from slug
                Verify JWT tenant matches
                          │
                          ▼
                Application code
              (tenant_id propagated via TenantContext)
                          │
                          ▼
                Firestore queries
              (filtered by tenant_id automatically)
                          │
                          ▼
              Firestore Security Rules
              (verify tenant_id match server-side)
                          │
                          ▼
                  Response to user
                (only their tenant's data)
```

## Tenant Slug Assignment

Platform admin assigns tenant slugs during onboarding. This provides:

- **Single point of control:** Platform team controls naming
- **Quality assurance:** No inappropriate or confusing slugs
- **Consistency:** Slugs follow naming conventions
- **Conflict resolution:** Platform handles any naming conflicts

Slug rules:

- Lowercase letters, numbers, and hyphens only
- 3-50 characters
- Cannot start or end with hyphen
- Must be unique across the entire platform
- Reserved slugs blocked: admin, api, www, app, support, etc.

Examples of valid slugs:
- sobha-dream-acres
- prestige-lakeside
- purva-the-waves

## JWT Token Structure

The JWT issued by Firebase Auth carries the tenant context required for authorization:

```json
{
  "sub": "firebase-user-id-12345",
  "email": "chandra@example.com",
  "tenant_id": "sobha-001",
  "tenant_slug": "sobha-dream-acres",
  "role": "resident",
  "household_id": "flat-A1204",
  "iat": 1717948800,
  "exp": 1717952400
}
```

The JWT is the **source of truth** for tenant identity. The URL provides UX (branding, routing, bookmarking) but the JWT is what the security system trusts.

This design prevents URL manipulation attacks:

```
Attacker scenario:
  User logged in to sobha-dream-acres.sportbook.chandraailabs.com
  Has JWT with tenant_id: "sobha-001"
  
  Attempts to access: prestige-lakeside.sportbook.chandraailabs.com/admin
  
  Middleware check:
    JWT tenant_slug = "sobha-dream-acres"
    URL subdomain = "prestige-lakeside"
    These do NOT match → 403 Forbidden
  
  No data leakage possible.
```

## Consequences

### Positive

- **Strong tenant isolation** via five-layer defense-in-depth
- **Cost effective** — single database scales to hundreds of tenants
- **Zero DNS burden on tenants** — wildcard handles everything
- **Professional UX** — each tenant feels they have their own site
- **Foolproof enforcement** — automated checks prevent vulnerable deployments
- **Industry-standard pattern** — recognizable and battle-tested
- **Compliance-ready** — supports DPDP Act and similar regulations
- **Future-proof** — supports both Indian and global expansion (combined with per-country deployments from ADR-0002)

### Negative

- **Defense-in-depth requires discipline** — five layers must be maintained
- **Initial setup complexity** — wildcard DNS, SSL, and Cloud Run mappings
- **Custom domain not supported** — some enterprise tenants might want it later
- **Single database** — noisy neighbor risk if one tenant has extreme load

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Developer bypasses repository pattern | Medium | Layer 5 static analysis blocks deployment |
| Firestore Security Rules misconfigured | Medium | Layer 4 tests verify on every commit |
| JWT signing key compromised | Very Low | Firebase rotates keys; mitigation via revocation |
| Wildcard SSL certificate expires | Low | Google auto-renews; monitoring alerts |
| Tenant slug collision | Low | Platform admin assigns; uniqueness enforced |
| Noisy neighbor degrades performance | Low | Firestore auto-scales; per-tenant rate limiting if needed |

## Alternatives Rejected

### Physical Isolation (Database Per Tenant)

**Why rejected:** Firestore allows ~100 named databases per project, capping growth. Per-tenant projects multiply GCP quotas and operational complexity. Per-tenant cost increases significantly. Not required for residential community SaaS — this is an enterprise/healthcare pattern.

### Collection-per-Tenant Hybrid

**Why rejected:** Provides no meaningful security benefit over logical isolation with proper guards. Risks hitting Firestore's 200 composite index limit. Non-standard pattern increases maintenance burden.

### URL Path-Based Tenant Identification

**Why rejected:** Cookie sharing weakens isolation. Less professional UX for residential community SaaS. Branding switches jarring. Harder to migrate to subdomain later.

### Custom Domains

**Why rejected:** Requires DNS configuration from tenants, adding technical burden and support overhead. Per-tenant SSL certificate provisioning complex. Coordinator explicitly chose to not impose technical requirements on tenants.

### JWT-Only Identification (No URL Indication)

**Why rejected:** Users cannot bookmark tenant-specific pages. Branding switches between tenants would be jarring. Login UX suffers. Industry consensus is against this approach.

## References

- Firestore Security Rules: https://firebase.google.com/docs/firestore/security/get-started
- Multi-tenant SaaS patterns: AWS SaaS Lens (Well-Architected Framework)
- Cloud Run domain mappings: https://cloud.google.com/run/docs/mapping-custom-domains
- DPDP Act compliance: https://www.meity.gov.in/data-protection-framework
- Industry examples of subdomain pattern: Slack, Shopify, GitHub Enterprise
- Defense-in-depth principle: NIST SP 800-160

## Related ADRs

- ADR-0001: Tech Stack (defines FastAPI middleware where Layer 3 lives)
- ADR-0002: Database Technology (Firestore Security Rules from Layer 1)
- ADR-0003: Build Tooling (CI/CD gates from Layer 5)
- Future ADR: Authentication & Authorization (will detail JWT structure)
- Future ADR: API Design Patterns (will detail repository pattern)
