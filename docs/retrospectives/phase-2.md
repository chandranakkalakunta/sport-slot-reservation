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
| 11 | All run.app URLs "404" for ~30h | /healthz is a GCP reserved path and was the sole canary in every cloud test; overlapped with a Google account review that silently removed services (confirmed via audit-log absence of deletes) | Liveness renamed to /health (2.6.2); account verified; redeployed; record corrected | Verify platform reserved paths at design time; differential tests vary one variable; complete the probe list past the first failure |

## The Cloud Run 404 investigation — and its real causes

After deployment, every run.app URL returned Google's HTML 404.
~30 hours of systematic elimination followed: service config, IAM,
org policy, propagation, hostname, region, client network — all
verified correct; request logs empty throughout.

Two overlapping causes, both confirmed:

1. /healthz is a documented GCP reserved path
(cloud.google.com/run/docs/issues) — Google's frontend intercepts
it on every *.run.app URL and returns 404 without reaching the
container. Every cloud test in the investigation probed /healthz
and only /healthz; /readyz was in the validation plan from the
start but was never executed because the plan halted at the first
failure. The "decisive" differential test was confounded: the
control service was probed at / while ours was probed at /healthz.
Liveness renamed to /health (2.6.2); the first /readyz ever sent
over the public edge returned 200.

2. A Google-side account review silently removed all three
services overnight Jun 11→12 — proven by audit log: services
existed at 02:15 UTC, were gone by morning, with ZERO
DeleteService entries (removal below the audit plane is
Google-internal only); the 05:33 redeploy logged CreateService,
confirming the name was free. The account was verified; the
redeployed service serves publicly.

The IAM and org-policy issues found along the way were real and
needed fixing, but cause 1 guaranteed a 404 in every probe even
after they were fixed, making it impossible to observe when
serving actually began working — which is why two true phenomena
produced 30 hours of false conclusions.

Lessons: (1) verify platform reserved paths at design time —
ADR-0006 chose /healthz from Kubernetes convention without
checking Cloud Run; (2) a differential test must vary exactly one
variable — ours varied two; (3) complete the probe list even
after the first failure — especially after the first failure;
one data point cannot localize a fault. One additional probe on
day one would have saved 30 hours.

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
by validation). All 11 issues produced durable rules.

## Carried forward

- RESOLVED 2026-06-12 (two overlapping causes — see investigation
  section): /healthz reserved-path confound + Google account
  review silently removing services. Account verified; service
  redeployed and serving publicly (/readyz 200, error envelopes
  verified over the edge).
- Known issue: containerized /readyz with mounted ADC unvalidated
  locally (likely HOME/mount path for system user) — revisit in
  Phase 5 when CI runs containers.
- deploy_cloud_run.sh: separate deploy from ensure-public-access.
- Strategist ground-truth access (GitHub/filesystem MCP) — agreed
  improvement, deferred; revisit before Phase 3.
