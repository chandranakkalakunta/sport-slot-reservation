# Phase 2 Retrospective — Backend API Foundation

Period: 2026-06-10 → 2026-06-12 · Sub-phases 2.1–2.7
Outcome: backend foundation complete and live-validated locally;
Cloud Run deployment built and configured correctly, public serving
blocked by a Google account-level hold (external; support case open).

## Issue log

| # | Symptom | Root cause | Resolution | Rule adopted |
|---|---------|-----------|------------|--------------|
| 1 | Unexpected branch with Phase 2 code | Work done outside protocol in a side session | Branch parked, ADRs written first, branch deleted after 2.3 | All work flows through the protocol; no side sessions |
| 2 | gcloud active account was org admin | chandra.n@ assumed to be a cloud identity; it is email/git only | Identity model documented in charter v1.1; app credentials via SA impersonation | Security docs must describe reality, not aspiration |
| 3 | Pre-flight expected no firebase.json; it existed | Strategist wrote pre-flights from summary docs, not verified state | Worker STOP-and-report; repo layout won | Pre-flight expectations come from verified state; summaries are maps, not territory |
| 4 | make verify-env passed but firebase CLI "not found" | Older terminal predated PNPM_HOME in zshrc | Fresh terminal | Shell sessions don't inherit config changes (re-confirmed) |
| 5 | slowapi 429 bypassed our error envelope (two rounds) | Middleware-layer exceptions never reach FastAPI exception handlers; slowapi hardcodes its handler | Subclassed middleware post-processes 429s into the envelope | Verify third-party library behavior at version before designing on it |
| 6 | /users/me 403 locally despite valid token | No .env existed; the tracked .env.example had been edited (real API key in a tracked file) | cp to .env, checkout template; near-miss, nothing committed | Setup instructions must say HOW to create files, not just name them; make dev-env added |
| 7 | Cloud Build 403 on staging bucket | Build ran as default Compute SA, not sa-cloud-build | --service-account flag + scripted IAM grants | Every gcloud mutation ships in a script — including hotfixes |
| 8 | Cloud Build logs-bucket FAILED_PRECONDITION, then unknown --logging flag | Custom build SAs default to GCS logging; logging is a build-config option, not a CLI flag (3 failed attempts from memory) | cloudbuild.yaml with CLOUD_LOGGING_ONLY | After two failed fixes, stop and read --help / docs before a third |
| 9 | allUsers IAM binding rejected | Secure-by-Default org policy (domain restricted sharing) | Project-scoped org-policy override; documented in charter v1.2 | Org-policy exceptions are scoped, documented, and reviewed at PROD boundary |
| 10 | Phase 2.7 docs fabricated after session interruption | Claude Code context compaction lost verbatim blocks; Worker reconstructed from memory and self-validated the fabrication | Independent grep validation caught it; full verbatim re-run (2.7.1) | After any session interruption, re-paste the full prompt; Worker self-validation cannot catch fabrication — independent validation is non-negotiable |

## The Cloud Run 404 investigation

After deployment, every run.app URL returned Google's HTML 404.
Systematic elimination over ~24h: service config (Ready=True,
ingress=all) → IAM (binding confirmed) → org policy (override
verified effective) → propagation (hours elapsed) → hostname
(recreation reproduces identical deterministic URLs — recreating
under a NEW name also 404'd) → region (asia-southeast1 also 404'd)
→ client network (mobile data identical; TLS terminated at genuine
Google frontend) → request logs (zero entries ever: requests never
reach the service).

Decisive differential: an established project under a different
account, same region, same network, served 200. Conclusion:
account-level serving hold on the new organization (created days
earlier) — a documented pattern for new accounts. All
customer-controllable surfaces verified correct; support case
filed with full evidence package.

Lesson: when configuration is verified correct and the symptom
persists, vary the variables you haven't varied — and know where
your control ends. The fastest path out was a differential
diagnosis, not another fix.

## Protocol amendments adopted (v1.0 → v1.1)

1. Pre-flight expectations MUST derive from verified state; Worker
   echoes every pre-flight check result explicitly.
2. Strategist verifies third-party library/API behavior (at the
   installed version) before designing around it; after two failed
   fixes, mandatory stop-and-read-docs.
3. Every cloud mutation ships in a version-controlled script —
   no exceptions for hotfixes or one-offs.
4. Validation plans must specify file-creation steps explicitly
   (how, not just what).
5. Strategist states expected counts as "report actual"; exact
   counting is the Coordinator's independent validation.
6. After any Worker session interruption, the full prompt is
   re-pasted in a fresh session; verbatim payloads must never be
   trusted to post-compaction context.

## What went right

Phase-gating caught every issue before it compounded. Worker
STOP-and-report behavior (issues 3, 5, 8) prevented bad guesses.
Independent Coordinator validation caught what reports missed —
including issue 10, where it was the only layer that could.
Cost: effectively ₹0 against a ₹5,000/month budget. Coverage 89%
against an 80% gate. Zero secrets committed (one near-miss caught
by validation). All 10 issues produced durable rules.

## Carried forward

- BLOCKER (external): Cloud Run serving hold — validation curls
  run when lifted; service sport-slot-api-b kept as live repro.
- Known issue: containerized /readyz with mounted ADC unvalidated
  locally (likely HOME/mount path for system user) — revisit in
  Phase 5 when CI runs containers.
- deploy_cloud_run.sh: separate deploy from ensure-public-access.
- Strategist ground-truth access (GitHub/filesystem MCP) — agreed
  improvement, deferred; revisit before Phase 3.
