# Disaster Recovery Runbook

- **Status:** Skeleton (PR-1a) — procedures below are complete where
  facts are known; drill execution and TODO-Coordinator items are
  outstanding.
- **Governing ADR:** [ADR-0038](../adr/ADR-0038-backup-and-disaster-recovery.md)
- **Last updated:** 2026-07-14

## 1. Scope, RTO/RPO, disaster classes

**RTO: 4 hours. RPO: 4 hours** (fixed premises, ADR-0038). Restore
scope is the **complete application** — data, secrets, infrastructure,
images, and identities. Restoring any one layer without the others
yields a non-functional app.

### Disaster classes in scope

| Class | Example | Primary defense |
|---|---|---|
| Corrupting write / application bug | Bad migration writes wrong data | Firestore PITR (near-zero RPO, 7-day window) |
| Bad deploy | Broken revision serving traffic | Cloud Run revision rollback; image rebuild (Layer 5) |
| Accidental/malicious deletion | Document or collection deleted | Firestore PITR |
| Database deletion | `(default)` database deleted | Delete protection (primary); daily backup schedule (worst-case 24h RPO — accepted residual, see ADR-0038) |
| Project loss | Project deleted/compromised | Full rebuild across all six layers into a new project |
| Secret loss/rotation need | Secret value compromised or lost | Layer 2 runbook-based re-issue (secrets are not backed up as values) |

### Explicit non-goal

Memorystore Redis (ephemeral locks/tokens) is **out of scope** —
restoring stale locks or expired tokens is wrong behavior, not missing
behavior. See ADR-0038 "Explicit non-goal — Redis."

## 2. Layer 1 — Firestore

### 2.1 PITR restore (preferred — corrupting write, bad deploy, accidental deletion)

PITR gives point-in-time recovery within the current retention window
(7 days once full depth accrues by 2026-07-21).

1. Identify the target restore timestamp (before the corrupting event).
2. Restore to a **new** database (PITR restore cannot overwrite the
   live `(default)` database in place):
   ```
   gcloud firestore databases restore \
     --source-database='(default)' \
     --destination-database=<restore-target-db-id> \
     --snapshot-time=<RFC3339 timestamp> \
     --project=sport-slot-dev
   ```
3. Validate restored data in `<restore-target-db-id>`.
4. Cut the application over to the restored database (config/env
   change), or export/import the needed collections back into
   `(default)` if a partial restore is preferred.
5. Decommission the scratch restore database once cutover is
   confirmed.

> **TODO-Coordinator:** confirm current GCP documentation for whether
> PITR restore can target the *same* database in place vs. requiring a
> new destination database — this procedure assumes new-database-only
> based on current understanding; verify before the timed drill.

### 2.2 Backup restore (database-deletion class only)

Daily backups (7-day retention) are the fallback when PITR itself is
unavailable — i.e., the database was deleted outright.

1. List available backups:
   ```
   gcloud firestore backups list --project=sport-slot-dev
   ```
2. Restore a backup to a new database:
   ```
   gcloud firestore databases restore \
     --source-backup=<backup-id> \
     --destination-database=<restore-target-db-id> \
     --project=sport-slot-dev
   ```

> **TODO:** Firestore backup restore is believed to be
> **same-project-only** (cannot restore a backup into a different GCP
> project). Verify against current GCP docs during drill design. If
> confirmed, the **project-loss** disaster class cannot use backup
> restore at all — Layer 1 recovery for project-loss depends on
> whichever layer-4/5 rebuild lands data into the new project first,
> or on the cross-project alternative below.

**Cross-project alternative (for project-loss class):** Firestore
managed export/import (`gcloud firestore export` / `import`) to/from a
GCS bucket works across projects, unlike backup restore. This path is
not currently scheduled (see ADR-0038 "Alternatives considered" — a
4-hourly export was rejected on cost grounds), but remains available
as a manual step during a project-loss drill or real recovery: export
from the surviving artifact (if any) or accept the daily-backup RPO
and re-import into the new project's database.

## 3. Layer 2 — Secrets

No out-of-band value backup exists (ADR-0038 §Layer 2). Recovery is
runbook-based re-issue, then Terraform-imported shell + a new secret
version added by the Coordinator (secret values are never handled by
automation per protocol §2.6).

| Secret | Origin | Recovery procedure |
|---|---|---|
| `redis-auth` | Memorystore AUTH string | `gcloud redis instances get-auth-string <instance> --region=asia-south1 --project=sport-slot-dev` (or `gcloud redis instances update --enable-auth` to force-rotate), then `gcloud secrets versions add redis-auth --data-file=-` |
| `resend-api-key` | Resend console | Re-issue key from the Resend dashboard, then `gcloud secrets versions add resend-api-key --data-file=-` |

**Obligation:** any new secret introduced to this project MUST be
added to this table in the same PR that introduces it, with its
re-issue path — or be explicitly flagged as irreplaceable (which would
itself justify revisiting the no-value-backup decision).

## 4. Layer 3 — Terraform rebuild

**Placeholder — completed in PR-1b (IAM-TF-CODIFY).**

PR-1b codifies the remaining imperative-only resources (four service
accounts, ~14 project-level IAM bindings, the Cloud Run service, the
Memorystore Redis instance, the Artifact Registry repository) so that
`terraform apply` becomes a credible from-scratch rebuild path. Until
PR-1b lands, a project-loss recovery requires manually recreating
those resources before `terraform apply` can complete the rebuild.
See ADR-0038 §Layer 3 for the full inventory and the Worker/Coordinator
division of labor for that sub-phase.

## 5. Layer 4 — GCS buckets

Versioned buckets: `sport-slot-dev-tfstate`, `sport-slot-dev-invoices`.
(`sport-slot-dev-frontend` and `sport-slot-dev-cloudbuild` are
explicitly excluded — rebuildable CI/deploy artifacts, no recovery
value from versioning; see ADR-0038 §Layer 4.)

### Restore a specific object version

1. List versions of the affected object:
   ```
   gcloud storage ls -a gs://<bucket>/<object>
   ```
2. Copy the desired noncurrent version back over the current object
   (or to a new path for review first):
   ```
   gcloud storage cp gs://<bucket>/<object>#<generation> gs://<bucket>/<object>
   ```
3. For `sport-slot-dev-tfstate` specifically: prefer `terraform state
   pull`/inspection before overwriting — a bad state file restore can
   desync Terraform from reality. Validate with `terraform plan`
   (Coordinator-run) immediately after any state object restore.

## 6. Layer 5 — Container images

Artifact Registry images (`sport-slot-repo`) are rebuildable from git;
no image backup/replication is maintained (single-region, 99% SLO —
region availability is the only protection).

### Rebuild path

1. Checkout the commit corresponding to the last known-good deployed
   revision (`git log`, or the Cloud Run revision's image tag/digest).
2. Trigger a rebuild:
   - **Preferred:** re-run the GitHub Actions workflow for that commit
     (Actions → the CI/CD workflow → "Re-run all jobs", or push a
     no-op commit if re-run isn't available for an old commit).
   - **Manual fallback:** build and push directly:
     ```
     gcloud builds submit --tag asia-south1-docker.pkg.dev/sport-slot-dev/sport-slot-repo/<image>:<tag>
     ```
3. Deploy the rebuilt image to Cloud Run (CI's normal deploy path, or
   `gcloud run deploy` manually if CI is unavailable).

## 7. Layer 6 — Firebase Auth identities

Firestore backups do **not** include Firebase Auth accounts (separate
store). Recovery is export/import-based, with a manual cadence until
automated (see AUTH-EXPORT-AUTO in backlog).

### Export (weekly manual cadence)

```
firebase auth:export auth-export-<date>.json --format=json --project=sport-slot-dev
```

Also record the password hash parameters from the Firebase Console
(Authentication → Users → the hash config shown for password-hash
export) — these are required to re-import password hashes correctly
and are **not** included in the export file itself.

### Import (restore)

```
firebase auth:import auth-export-<date>.json --hash-algo=<algo> \
  --hash-key=<base64-key> [other hash params] --project=<target-project>
```

**Required:** both the export bundle and the password hash parameters
MUST be stored off-project (a project-loss disaster takes the source
project's own storage with it).

> **TODO-Coordinator:** choose the secure off-project storage location
> for the weekly export bundle + hash parameters (options to evaluate:
> a separate GCP project's GCS bucket with CMEK, or an equivalent
> access-controlled store outside this project's blast radius).

**Accepted residual risk:** identities created after the most recent
export are lost under the project-loss class; affected users
re-register.

## 8. DNS (Namecheap)

### Record inventory

> **TODO-Coordinator:** fill in current values from the Namecheap
> dashboard.

| Record | Type | Target | Current TTL |
|---|---|---|---|
| Wildcard (`*.<domain>`) | A | Load Balancer static IP: TODO-Coordinator | TODO-Coordinator |
| Certificate Manager DNS authorization | CNAME | TODO-Coordinator | TODO-Coordinator |

### Rebuild procedure

1. Provision a new global static IP for the Load Balancer (Terraform-
   managed — see `terraform/load_balancer_network.tf`).
2. Update the wildcard A record in Namecheap to point at the new
   static IP.
3. If certificates need re-authorization (new Certificate Manager
   resource), create the new DNS authorization CNAME record in
   Namecheap matching the value Certificate Manager issues.
4. Wait for DNS propagation (bounded by TTL) and certificate issuance
   before considering the rebuild complete.

**Recommendation:** lower TTLs to 300–600s ahead of any planned DR
drill or migration, so a real cutover doesn't spend hours waiting on
long-TTL propagation. Revert to a higher TTL afterward if the shorter
TTL has a query-volume cost implication worth avoiding.

## 9. Timed drill plan

**A restore runbook that hasn't been executed is not a DR plan**
(ADR-0038 "Deliverable and proof"). Executed at PR-1 closure, after
both PR-1a and PR-1b have merged and applied.

### Plan

1. **Environment:** a separate scratch GCP project (zero blast radius
   to `sport-slot-dev`).
2. **Scope:** all six layers, in dependency order:
   1. Terraform rebuild (Layer 3) — project skeleton, IAM, networking.
   2. Firestore restore (Layer 1) — PITR or backup restore into the
      scratch project (see the Layer 1 TODO on cross-project backup
      restore — this drill is exactly where that gets answered).
   3. Secrets (Layer 2) — re-issue and populate shells.
   4. GCS buckets (Layer 4) — recreate/restore as needed.
   5. Container images (Layer 5) — rebuild via CI against the scratch
      project's Artifact Registry.
   6. Firebase Auth (Layer 6) — import the most recent export.
   7. DNS (chapter 8) — point a throwaway subdomain at the scratch
      environment to validate the full path end-to-end (not the
      production domain).
3. **Measurement:** wall-clock time from "declare disaster" to "app
   serving correct traffic in the scratch project," recorded against
   the 4-hour RTO target.
4. **Output:** drill report appended to this runbook (date, duration,
   deviations from the procedures above, fixes needed before the next
   drill) and any corrective backlog items filed.

> **TODO-Coordinator:** schedule the drill date once PR-1b has merged
> and applied.
