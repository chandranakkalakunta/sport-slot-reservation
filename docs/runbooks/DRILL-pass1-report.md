# DR Drill — Pass 1 Report (Empty Rebuild Shakeout)

**Date:** 2026-07-22 → 2026-07-23
**Target:** `slot-sense-dev-01` (fresh GCP project, 189872798775)
**Scope:** Layers 3/4/5 (Terraform infra, buckets, container image) +
minimal Layer 2 (secret values). Layers 1/6 (Firestore data, Auth
identities) and DNS/cert cutover deferred to Pass 2.
**Outcome:** ✅ **PASS** — a fresh project was rebuilt to a running,
health-passing SlotSense stack from Terraform config.

---

## Result

- **111 resources** created from config into an empty project
- Cloud Run revision `sport-slot-api-00002-nhc` **Ready / ACTIVE**,
  serving 100%
- **Zero warnings or errors** in Cloud Run logs post-start
- `terraform plan` → **"No changes"** (config = state = live)
- Container image rebuilt from source via Cloud Build (Layer 5 ✓)

ADR-0038's central claim — *"`terraform apply` is the rebuild path"* —
is now **demonstrated**, not asserted.

## Timing (indicative, not a clean RTO)

| Stage | Wall clock |
|---|---|
| Project bootstrap (create, billing, APIs, state bucket, init) | ~10 min |
| Bootstrap-group apply (21 APIs + registry + build SA) | ~2 min |
| Image build & push (Cloud Build) | ~1 min |
| Main apply (87 resources; Redis 9m35s, backend service 2m35s) | ~15 min |
| Recovery from in-run issues (secrets, taint, buckets) | ~30 min |
| **Total machine time** | **~28 min** |
| **Total elapsed incl. debugging** | ~2.5 h |

Well inside the 4h RTO even with first-contact friction. A clean
scripted run should land near the machine-time figure. **The measured
RTO from a scripted, uninterrupted run remains to be captured.**

---

## Two passes, workaround count

The drill was run twice. The first attempt (into `slot-sense-dev`,
deleted) surfaced 6 blocking gaps; those were codified in **PR-B**;
the second attempt (into `slot-sense-dev-01`) needed only 3.

### Fixed by PR-B and validated live in Pass 1

| # | Gap (first attempt) | Permanent fix | Verified |
|---|---|---|---|
| 1 | Artifact Registry 403 — API not enabled; `-target` skipped API resources | `depends_on = [google_project_service.enabled_apis]` on foundational resources | ✅ APIs enabled by TF, no manual `gcloud services enable` |
| 2 | Cloud Build 403 — default Compute SA lacked bucket access | Codified `roles/cloudbuild.builds.builder` on `<project_number>-compute@` | ✅ auto-created, build succeeded unattended |
| 3 | Cloud Run image pointed at old project/tag | Parameterized `${var.project_id}/${var.artifact_repo_name}/...:${var.bootstrap_image_tag}` | ✅ resolved to new project's image |
| 4 | AR repo hardcoded `sport-slot-repo` | `var.artifact_repo_name` (new envs `slot-sense-repo`) | ✅ created as `slot-sense-repo` |
| 5 | `allUsers` frontend binding blocked by org policy | Codified project-scoped `google_org_policy_policy` (ADR-0031 exception) | ✅ binding created (after propagation delay) |
| 6 | tfstate bucket 409 — created by bootstrap AND declared in TF | Removed from Terraform (bootstrap-script artifact) | ✅ no conflict |

### Remaining gaps found in Pass 1 (→ PR-C)

| # | Gap | Permanent fix | Status |
|---|---|---|---|
| 7 | **Secret values populated after Cloud Run creation** → service created broken, Terraform **tainted** it, `prevent_destroy` then deadlocked recovery (needed manual `untaint` + forced revision) | Secret population is a **hard prerequisite** before the Cloud Run apply — enforce in bootstrap sequence | OPEN |
| 8 | Cloud Build staging bucket `<project>-cloudbuild` (hyphen) never created — `build_push.sh` requires it explicitly via `--gcs-source-staging-dir`; plain `builds submit` uses Google's `<project>_cloudbuild` (underscore) | Terraform creates `google_storage_bucket.cloudbuild_staging` + IAM `depends_on` it (one-time import in sport-slot-dev) | OPEN |
| 9 | "Coordinator SMS" channel is a manual console pre-req; `observability.tf` data-source lookup fails the **entire plan** without it | Decide: keep manual, or convert to a TF resource, or make new-env alerting email-only | OPEN (decision) |
| 10 | Org-policy exception needs propagation time before the `allUsers` binding succeeds (failed first attempt, worked minutes later) | Retry/wait in the bootstrap script | OPEN |

---

## Findings beyond the rebuild itself

**1. `deploy_cloud_run.sh` silently reverts ADR-0041 D15.**
The script hardcodes `--max-instances=2`. Terraform sets 10 (per
ADR-0041); every CI deploy resets it to 2. **maxScale 10 has never
actually held in production.** This explains the recurring
`max_instance_count = 2 -> 10` seen across multiple plans this phase —
it was not drift Terraform failed to apply, it was Terraform and CI
fighting, with CI writing last. Fix: remove `--min-instances` /
`--max-instances` from the script; Terraform owns scaling (D7 model:
CI owns image + env, Terraform owns template config).

**2. The deploy pipeline is single-environment.**
`deploy_cloud_run.sh` and `build_push.sh` hardcode
`PROJECT="sport-slot-dev"`, `sport-slot-repo`, and the domain. Even
with Terraform multi-env (PR-A/PR-B), **CI cannot deploy to a new
environment.** Parameterizing the scripts + workflow is PR-C's main
body of work.

**3. Platform admin bootstrap is unsolved — the most important gap.**
A brand-new environment has **no admin user**. DR runbook Layer 6 only
covers *restoring* identities from a Firebase Auth export; there is no
first-time-admin path. A rebuilt environment is therefore not usable
without a documented, scripted admin-creation step (Firebase Admin SDK:
create user + role claim + Firestore admin doc; password generated to
Secret Manager or via first-login reset — never in TF/tfvars).

**4. Local environment hazards observed (worth runbook notes).**
- After a drill, the local `.terraform` still points at the drill
  backend — re-init before touching dev state.
- macOS TCC can silently revoke Terminal's access to `~/Documents`
  mid-session (`ls: Operation not permitted` while Finder works).
- A live secret value was exposed during the drill and required
  rotation — reinforces never echoing secret values.

---

## Runbook corrections (docs/runbooks/disaster-recovery.md)

- **§4.1** — replace the "`-target` everything except Cloud Run" step
  with an explicit **bootstrap group**: APIs + Artifact Registry +
  Cloud Build SA IAM + cloudbuild staging bucket, applied first; then
  image build; then **secret population**; then the main apply.
- **§4.1** — secret population moves *before* the Cloud Run apply
  (hard prerequisite, finding #7).
- **§4.2** — the default Compute SA is **not unused**: it is Cloud
  Build's default identity in new projects. Correct the exclusion
  table.
- **§4.1** — add the org-policy propagation wait before the public
  bucket binding.
- **Layer 6** — add a first-time platform-admin bootstrap procedure
  (finding #3); current text assumes an export exists.
- Firestore TODOs (PITR in-place semantics, cross-project backup
  restore) remain unanswered — Pass 2 scope.
- DNS record inventory (§8) still unfilled — Pass 2 / cutover scope.

---

## Definition of done — the single-touch rebuild

The drill's real deliverable is not this report but a
**`drill-bootstrap.sh`** encoding the now-proven sequence:

```
project create → billing link → bootstrap APIs → state bucket →
terraform init -backend-config → firebase add → SMS channel →
bootstrap-group apply → SECRET POPULATION → image build →
main apply → admin bootstrap → health verify → clean-plan check
```

Idempotent, retry-safe, one command. PR-C closes the config/script
gaps; the script encodes what genuinely cannot be Terraform. A timed,
uninterrupted run of that script produces the authoritative RTO.

## Next

1. **PR-C** — cloudbuild bucket in TF; deploy/build script
   parameterization; remove `--max-instances`; secret-ordering; org-
   policy wait.
2. **Platform admin bootstrap** — design + script (blocks a usable
   fresh environment).
3. **`drill-bootstrap.sh`** — encode the sequence; timed run for RTO.
4. **Pass 2** — Firestore export/import, Auth export/import with hash
   params, DNS/cert cutover; answers the two open Firestore TODOs.
5. Decide the fate of `slot-sense-dev-01`: keep as the standing dev
   replacement (per the naming migration) or delete and rebuild from
   the script once PR-C lands.
