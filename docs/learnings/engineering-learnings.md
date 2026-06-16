# SportSlotReservation — Engineering Learnings (Phases 2–5.4b)

A working log of what bit us, what we under-specified, and the rules we adopted
so the next project starts smarter. Organized by theme rather than chronology,
because the *patterns* matter more than the order they appeared.

---

## 1. Cross-layer rules must be mirrored, or they rot

The single most recurring class of bug: a rule implemented correctly in one
layer, never propagated to its sibling layer, surfacing the moment a new code
path exercised the gap.

- **The "bare host → trust the JWT" rule** was added to the *backend* tenant
  cross-check in 4.5a, but the *frontend* branding resolver was written before
  that surface existed and never got the parallel treatment. Result: the app
  stayed default-blue on `.web.app` (4.6.1). Same logical rule, two layers,
  fixed one sub-phase apart.
- **The dev-tenant pin** (`dev_tenant_slug` / `SPORTSLOT_DEV_TENANT_SLUG`) lived
  in *both* the backend dependency and the frontend `VITE_DEFAULT_TENANT_SLUG`
  *and* the test conftest. We killed it in the backend (5.3.1) but it lingered
  in tests until 5.4a swept it. One concept, three homes.

**Rule adopted:** when a rule concerns a boundary (host→tenant, auth→claim,
error→message), write down *every* layer that encodes it, and change them
together. A rule that exists in one layer and not its mirror is a latent bug
with a fuse already lit.

---

## 2. Deployed ≠ local: the environment-parity tax

We were repeatedly surprised that something working locally failed when
deployed, because the two environments differ in ways that don't show up until
exercised.

- **Stale image 403 (4.5a):** the deployed Cloud Run image predated the
  X-Forwarded-Host middleware; the frontend on `.web.app` called the *old*
  backend. "Committed" and "deployed" are different events.
- **IAM least-privilege gap (5.4b deploy):** user provisioning worked locally
  (dev impersonates `sa-firebase-admin`, which has Firebase Auth rights) but
  500'd in the cloud (`sa-cloud-run` was scoped to Firestore only, no
  `identitytoolkit` permission). The capability that worked under dev
  credentials simply wasn't granted to the deployed service account.
- **One Firestore, not two:** a conceptual clarification that took a beat — dev
  and cloud share the *same* `(default)` Firestore in `sport-slot-dev`; local
  `make run-dev` writes to cloud via impersonation. No separate "local DB."

**Rules adopted:**
- After *any* backend change, `make build-push && make deploy-dev` before
  validating on `.web.app`. (This is exactly what CI/CD will automate away —
  it makes "committed" and "deployed" the same event.)
- When an operation needs a Google API beyond Firestore (Firebase Auth, Storage,
  Pub/Sub…), verify the *deployed* service account has the role — not just your
  dev impersonation. Dev creds are more powerful than the runtime SA by design
  (least privilege), so dev success is not deploy success.
- Keep an explicit map of "which identity runs where": dev = `sa-firebase-admin`
  (broad), Cloud Run = `sa-cloud-run` (narrow). Privilege gaps live in that gap.

---

## 3. Things only break when you exercise the second instance

Multi-tenancy, multi-user, multi-anything bugs hide until you create the *second*
one, because the first accidentally matches every default.

- **Multi-tenant auth (5.3.1):** every test until rvrg used the *demo* tenant.
  The `dev_tenant_slug=demo` pin made all localhost auth resolve to demo, so
  demo users worked and the pin was invisible. The instant a non-demo tenant's
  admin logged in, every authenticated call 403'd. The bug was always there;
  only the second tenant revealed it.

**Rule adopted:** validate multi-X features with at least *two* X's, deliberately
different, as early as possible. One instance proves the happy path; two prove
the *isolation*. Seed a second tenant the moment multi-tenancy exists, not at
the end.

---

## 4. Least privilege works — which means it will surprise you

The IAM 500 (§2) was not a failure of the security model; it was the security
model *succeeding*. `sa-cloud-run` couldn't create Firebase users because it was
never granted that power. The "fix" (granting `roles/firebaseauth.admin`) is a
deliberate privilege escalation that must be *documented and time-boxed*, not
quietly applied.

**Rules adopted:**
- Treat every privilege grant as a decision with a closure plan. We recorded:
  "`sa-cloud-run` holds `firebaseauth.admin` because synchronous provisioning
  runs in the main API (ADR-0016); when provisioning moves to a background job
  (Phase 7), the privilege moves with it." Elevated scope with an expiry.
- A least-privilege architecture means you *will* hit "insufficient permission"
  on first use of a new capability in production. Expect it; read the runtime
  SA's roles, don't assume.

---

## 5. Error opacity costs real time

The `VALIDATION_FAILED` envelope swallowed Pydantic's field-level detail,
turning a one-field body mismatch (`name` vs `display_name`) into a multi-message
debugging detour: three 422s and two greps to discover the model wanted
`display_name`. The generic "Something went wrong" frontend fallback did the
same for the 500.

**Rules adopted:**
- In development, surface the *specific* validation detail (which field, why).
  We added a `detail` array to the envelope (5.4b). The cost of leaking field
  names in dev is trivial; the cost of hiding them is measured in round-trips.
- Frontend error fallbacks ("Something went wrong") should, in dev, log or show
  the underlying code. A generic message is correct for users and useless for
  debugging — give yourself the real one in dev.
- Validation curls written from the *prompt* (not the actual code) silently
  break when a field is renamed. Read the real model before validating.

---

## 6. Missing / under-specified requirements (caught mid-flight)

These were requirements that *weren't* in the original plan and surfaced only
because someone questioned the design. Each should have been an explicit
up-front decision.

- **Deletion / retention lifecycle (whole of ADR-0017).** The original roadmap
  had create flows but no *delete*. Raised mid-5.2. Turned into a three-stage
  ACTIVE→INACTIVE→PURGED lifecycle, an authority matrix, auto-cancel of future
  bookings, and a deferred purge job. A core CRUD verb was simply absent from
  the plan.
- **Logo in branding.** Branding shipped with name + colors; logo was missing
  until questioned. Resolved as a URL field now, file-upload deferred.
- **`flat_number` not applicable to admins.** The shared user model forced a
  flat number on tenant admins (the meaningless `E-1111`). The "one model for
  all users" simplification over-applied a resident-only field.
- **Platform-admin catalog management.** Who adds a *new* facility type (squash,
  pickleball) at runtime? Nobody, currently — catalog management UI was
  deferred. Tracked with a trigger condition ("when a tenant needs a non-seeded
  sport") rather than left implicit.
- **Multi-tenant admin (one admin → many tenants).** A legitimate use case
  (a support team across societies) that the one-user-one-tenant model forbids.
  Correctly deferred (it's a security-sensitive change to the auth model +
  every isolation check) — but it was never in scope and had to be recognized.
- **Composite index wiring.** The index was *defined* (`firestore.indexes.json`)
  but `firebase.json` had no `firestore` block, so it couldn't deploy. Defined
  ≠ deployable. Fixed in 5.4a.

**Rule adopted:** for every entity, explicitly walk the full lifecycle (create,
read, update, *deactivate*, *delete/retain*) and the full actor matrix (who can
do each, across tenant boundaries) at design time. The verbs and actors we
*didn't* enumerate are exactly the ones that became mid-flight ADRs.

---

## 7. Identity bootstrapping & credential hygiene

- **Bootstrapping paradox:** the first platform admin can't be created by a
  platform admin → seed script. Same for the facility catalog. Recognize
  "who creates the first one?" as a design question for any self-referential
  authority.
- **Generated-password + force-change** is a clean uniform model (no admin-chosen
  weak passwords, one provisioning path for all roles). The forced-change flag
  lives on the profile (Firebase has no native "must change" flag).
- **Lost the superadmin password** because it's shown once. A dev-only nicety
  (write seeded creds to a gitignored file, or a documented reset one-liner)
  would save the scramble. Generated-once credentials need a *recovery* story,
  not just a creation story.
- **Identity separation:** cloud identity (`admin@`) ≠ app platform-admin ≠
  tenant identities. Keeping these distinct avoids conflating "can manage GCP"
  with "is a superadmin in the app." (Minor drift to reconcile: seed used
  `admin@sportbook` vs ADR-0014's stated `superadmin@` — a doc/code mismatch
  that should be caught at seed-script-review, not discovered at login.)

---

## 8. ADR discipline paid off — and where it had gaps

The "decision → ADR → then code" rhythm repeatedly saved us: ADR-0014's
route-vs-host gating relaxation, ADR-0016's deployment-placement note, ADR-0017's
whole lifecycle. But two ADRs written days apart had a **latent contradiction**:
ADR-0007 said platform_admin is host-restricted; ADR-0014 relaxed it to
route+role for dev. The code followed the older one; the conflict surfaced the
instant a superadmin first authenticated (5.2.1).

**Rule adopted:** when a new ADR *modifies* an earlier decision, explicitly note
the supersession in *both* ADRs, and grep the code for the old rule's
enforcement. A relaxation that isn't propagated to the code is just a document
disagreeing with reality.

---

## 9. The three-agent protocol: what worked

- **Read-before-edit (STEP 0)** on every prompt touching existing code caught
  structural drift between the plan and reality (model field names, repo shapes,
  the actual cross-check logic). The heaviest prompts leaned hardest on this and
  were the most accurate.
- **The Worker's judgment deviations were consistently the right kind:** setting
  `tenant_slug` to the looked-up value instead of `None` (would have broken auth
  for every provisioned user); fixing `??`→`||` for env-var determinism; catching
  that a test passed for a *different* reason after a gate removal. "Transcribe
  faithfully, but STOP when faithful transcription breaks the system" worked.
- **Live validation as the gate that matters.** Tests passed at every sub-phase,
  but the bugs that bit (multi-tenant 403, IAM 500, branding-blue) were all found
  by *running it*, not by the suite. Green tests are necessary, not sufficient.

**Rules adopted:** keep read-before-edit mandatory for edits to existing code;
treat Worker deviations as signal (review each, they often reveal a prompt bug);
and always finish a sub-phase with a live, multi-instance validation pass — the
suite guards regressions, the live pass finds the gaps the suite didn't imagine.

---

## 10. Practical/operational papercuts (small but recurring)

- **ADC expiry in dev** ("Reauthentication is needed") — routine, not a bug; the
  cost of no static keys. Re-auth with the impersonation command. Worth a
  one-line runbook entry and a make target.
- **Firebase ID tokens last 1 hour** — `AUTH_INVALID_TOKEN` on a previously-
  working token is almost always expiry; re-mint.
- **`curl -s` hides connection failures; `python3 -m json.tool` chokes on
  `-w "%{http_code}"`** — small harness frictions that masquerade as API
  failures. Know your tools' failure modes.
- **`make deploy-dev` (backend → Cloud Run) vs `make deploy-hosting`
  (frontend → Firebase Hosting)** are independent; a feature spanning both needs
  both deployed, in sync.

---

## Top 5 carry-forward rules for the next project

1. **Mirror cross-layer rules explicitly.** A boundary rule (host→tenant,
   auth→claim) lives in multiple layers; enumerate and change them together.
2. **Deployed ≠ local.** Verify the *runtime* service account's permissions and
   the *deployed* image version before trusting a cloud test. Automate the
   deploy so committed = deployed.
3. **Walk every entity's full lifecycle and actor matrix at design time.** The
   verbs (delete/retain) and actors (cross-tenant) you skip become mid-flight
   ADRs. Deletion is not optional.
4. **Validate multi-X with two X's, early.** Isolation bugs only appear with a
   second tenant/user. Seed the second one when the feature lands, not at the end.
5. **Make errors loud in dev.** Surface validation field detail and real error
   codes; generic messages cost round-trips. Read the real model before writing
   validation calls.

---

*Compiled mid-Phase-5 (through 5.4b). Living document — append as Phase 5
completes and Phases 6+ proceed.*

---

# APPENDIX A — Phase 5 (Admin & Onboarding) additions

Phase 5 reinforced several earlier themes and added new ones. Appended on
project-day for Phase 5 close.

## 11. A security gate must be one unbypassable choke point

The forced-password-change requirement was first implemented as a check in the
*Landing* component (route `/`). Every other authenticated route was auth- and
role-gated but never checked the flag — so a tenant admin reaching `/tenant`
directly (post-login nav, refresh, or typed URL) bypassed the mandatory change
entirely. The fix that *held* moved the check into the shared route guards
(`ProtectedRoute`, `TenantAdminRoute`), making it impossible to render any
authenticated screen with the flag set. A follow-on bug: after a successful
change, a stale cached profile bounced the user back — fixed by invalidating the
profile query on success.

**Rules:** (a) a security/lifecycle gate belongs at the *single choke point* all
protected routes pass through, never as a per-route check — locking one door
leaves the others open. (b) After a state change that a gate reads, invalidate
the cache the gate consults, or it will re-fire on stale data.

## 12. The deployed runtime identity is weaker than your dev identity — on purpose

User provisioning worked locally but 500'd in the cloud. Cause: local dev
impersonates `sa-firebase-admin` (broad — can manage Firebase Auth), but the
deployed Cloud Run service runs as `sa-cloud-run` (narrow — Firestore only, by
least-privilege design). Creating users calls Firebase Auth admin APIs the
runtime SA wasn't granted. The fix (grant `firebaseauth.admin`) is a deliberate,
time-boxed privilege escalation, recorded in the charter to be narrowed when
provisioning moves to a background job (Phase 7).

**Rule:** least privilege guarantees that a new capability will fail on first
*deployed* use even when it works in dev. When an operation needs a Google API
beyond your baseline (Auth, Storage, Pub/Sub), grant it to the *runtime* SA and
document the grant with a closure plan — don't infer from dev success.

## 13. Stop fixing environment limitations in the wrong environment

Multi-tenant branding was "fixed" three times and kept resurfacing, because the
real cause is the absence of tenant subdomains on localhost/`.web.app` — which
only Phase 7 (LB + wildcard domain) provides. The branding *data* was always
correct; only the *applied theme* on non-subdomain hosts was wrong. The right
move, reached late, was to stop fixing it in dev and defer verification to the
environment where it can actually be correct.

**Rule:** distinguish a bug from an environment limitation. If a fix keeps
half-working and resurfacing, ask whether the environment can even express the
correct behavior. If not, document the limitation and defer to the environment
that can — continuing to patch is whack-a-mole.

## 14. Diagnose with one decisive observation before proposing a fix

Phase 5's hardest stretch was a "many issues" pile that felt overwhelming.
Triaging each symptom with a single decisive observation — the `code` in a 403
body, a `/users/me` response, a 200-vs-500 on one request, the actual deployed
image tag — repeatedly collapsed the pile: several "bugs" were stale deployments,
one was an environment limitation, one was a non-issue the user retracted, and
only a few were real. Guessing-and-patching would have churned through all of
them; one observation each sorted signal from noise.

**Rule:** when symptoms cluster, resist the fix-everything prompt. Get one
decisive datum per symptom first (response body, log line, deployed version).
The real-bug list is usually a fraction of the apparent one, and the data tells
you *which* layer to fix instead of guessing.

## 15. Defer UI optimization to a dedicated pass, not piecemeal

The card-per-user list works for ten users and collapses at a thousand. The
decision was *not* to optimize it mid-build (which would optimize a moving target
and get rebuilt as new screens land) but to do one coherent UI-scalability pass —
table layouts, cursor pagination, search, filters, a shared list component —
once the functional surface is complete.

**Rule:** cross-cutting UI/UX optimization is best done once, against a stable
functional surface, as a dedicated pass — not retrofitted per-screen during
feature build. Track the need; schedule the pass.

## Updated top carry-forward rules (Phases 2–5)

1. Mirror cross-layer rules explicitly; a boundary rule lives in several layers.
2. Deployed != local: verify the runtime SA's permissions and the deployed image
   version. Automate deploys so committed = deployed (Phase 6 CI/CD).
3. Walk every entity's full lifecycle and actor matrix at design time; the verbs
   (delete/retain) and actors (cross-tenant) you skip become mid-flight ADRs.
4. Validate multi-X with two X's, early — isolation bugs need a second instance.
5. Make errors loud in dev; diagnose with one decisive observation before fixing.
6. A security gate is one unbypassable choke point; invalidate caches it reads.
7. Distinguish bugs from environment limitations; don't patch the wrong env.
8. Defer cross-cutting UI optimization to a dedicated post-functional pass.

*Appended at Phase 5 close. Continue through Phases 6+.*

---

# APPENDIX B — Phase 6 (CI/CD) additions

Phase 6 built the keyless deployment pipeline (WIF + Cloud Run + Firebase
Hosting REST API). New themes from the CI/CD surface. Appended at Phase 6 close.

## 16. Pin every toolchain version explicitly so local == clean CI

Phase 6 surfaced five toolchain-drift mismatches — all invisible locally,
all hard failures in CI's clean environment: linter working directory, test
hermeticity (no ADC in CI), pnpm v9-vs-v11, Node 20-vs-22, and interactive
firebase-tools vs. keyless CI. In every case the local environment silently
masked the mismatch; CI's cold, clean environment revealed it.

The root fix was to encode the correct version as an explicit declaration in
the project — `packageManager: pnpm@11.5.2` + `engines.node: >=22.13` in
`package.json`, `.python-version` in the backend, `working-directory` in the
workflow. Once the version is a checked-in fact, both local and CI read from
the same source of truth.

**Rule:** pin every toolchain version explicitly in the project (not in CI
config alone, not ambient from the local environment). `packageManager`,
`engines.node`, `.python-version`, and `working-directory` are two-line fixes
that prevent entire classes of "works locally, fails in CI" surprises. Add them
at project creation, not when CI first breaks.

## 17. Least-privilege discovered wall-by-wall and Terraform-codified beats "grant editor"

The CI pipeline needed 10 distinct IAM bindings across two principals (the WIF
principalSet and the impersonated SA). None were pre-granted. Each was
discovered by a precise permission error, confirmed by reading the error body,
and added as a single Terraform resource with a comment explaining why. The
result is an exact, auditable inventory: `wif_iam.tf` documents what CI can do
and what it cannot.

The alternative — granting `editor` to the CI principal — would have
immediately unblocked every failure but left no trace of which permissions are
actually used, why, or what the blast radius is if the WIF configuration were
misconfigured.

**Rule:** add IAM grants one-at-a-time, only when a failure proves the need,
and record each grant in version-controlled Terraform with a comment explaining
the exact operation that requires it. "Grant editor and move on" is fast today
and a security debt forever. Wall-by-wall is slow once and correct permanently.

## 18. firebase-tools cannot consume WIF external_account ADC for deploys

firebase-tools 15.x's internal token manager only understands `firebase login`
(interactive user token) and `login:ci` (deprecated refresh token). When the
`GOOGLE_APPLICATION_CREDENTIALS` file contains a WIF `external_account`
credential, firebase-tools finds "No OAuth tokens found" and crashes on
`undefined.access_token`. This is not a configuration error; it is a hard
limitation of the tool's token manager.

The correct keyless path for CI Firebase Hosting deploys is the Firebase Hosting
REST API (`firebasehosting.googleapis.com/v1beta1`) with an SA-impersonated
OAuth2 access token. `firebase-tools` is the right tool for human-interactive
use where `firebase login` works; it is the wrong tool for keyless CI.

**Rule:** for any Firebase Hosting deploy in CI without a JSON key, skip
firebase-tools entirely and drive the REST API directly. Check any CLI tool's
token-manager documentation before building a keyless CI path around it; "works
with ADC" is not the same as "works with WIF external_account ADC."

## 19. SA impersonation shifts the effective caller identity for all downstream IAM checks

When `google-github-actions/auth@v3` mints a token via SA impersonation and
that token is used to call a REST API, the *impersonated SA* is the effective
caller for every IAM check the API performs — not the WIF principalSet. This
matters when the API call includes `X-Goog-User-Project`: the service usage
check runs against the SA's own IAM bindings.

In Phase 6, the WIF principalSet had `serviceUsageConsumer` (6.1.1). After SA
impersonation was introduced (6.2.14), the same REST call started returning 403
`USER_PROJECT_DENIED` because `sa-firebase-admin` lacked the role. Two
identical permissions, two different principals, discovered in sequence.

**Rule:** when you introduce SA impersonation, audit every IAM check the
downstream call performs and verify it passes for the *SA's* identity, not just
the WIF principal. Keep a mental (or documented) map of "which identity is the
effective caller at each step" — it changes the moment impersonation is in the
chain.

## 20. Loud, specific errors are how least-privilege converges; never silence auth stderr

Phase 6's IAM discovery worked because every failure was loud: the `api()`
helper in `deploy_hosting_rest.sh` always printed HTTP status + response body on
≥400. The 401→400→403→success progression each took one sub-phase. Each was
immediately actionable.

The contrasting anti-pattern appeared in `deploy_cloud_run.sh`: the Redis
describe command had `2>/dev/null || true`, silently converting a permission
error ("caller lacks redis.viewer") into an empty string that looked like "Redis
not found." The symptom was far removed from the cause.

**Rule:** never silence stderr on auth/permission calls. `2>/dev/null || true`
on a gcloud or curl command is a diagnostic time bomb: the next person sees
an empty result and debugs the wrong thing. Let permission errors be loud; they
are the signal that tells you exactly what to grant.

## Updated top carry-forward rules (Phases 2–6)

1. Mirror cross-layer rules explicitly; a boundary rule lives in several layers.
2. Deployed != local: verify the runtime SA's permissions and the deployed image
   version. CI makes committed = deployed.
3. Walk every entity's full lifecycle and actor matrix at design time; the verbs
   (delete/retain) and actors (cross-tenant) you skip become mid-flight ADRs.
4. Validate multi-X with two X's, early — isolation bugs need a second instance.
5. Make errors loud in dev and in CI scripts; diagnose with one decisive observation.
6. A security gate is one unbypassable choke point; invalidate caches it reads.
7. Distinguish bugs from environment limitations; don't patch the wrong env.
8. Defer cross-cutting UI optimization to a dedicated post-functional pass.
9. Pin every toolchain version explicitly in the project (packageManager,
   engines.node, .python-version). Add at project creation, not when CI breaks.
10. Grant IAM wall-by-wall, one permission per proven failure, in Terraform with
    a comment. Never silence auth stderr — the error is the diagnosis.
11. For keyless CI Firebase Hosting: skip firebase-tools, use the REST API +
    SA-impersonated OAuth2 token. SA impersonation shifts the IAM caller identity
    for all downstream checks.

*Appended at Phase 6 close.*
