# Observability & Alerting Runbook

- **Status:** Baseline shipped (PR-2, pending Coordinator apply)
- **Governing ADR:** [ADR-0040](../adr/ADR-0040-observability-and-alerting.md)
- **Last updated:** 2026-07-17

## What exists

All Terraform-managed in `terraform/observability.tf` (ADR-0040). Every
resource is a **create** — nothing pre-existing to reconcile against.

| Alert | Condition | Window | Notifies |
|---|---|---|---|
| 5xx error rate | > 5% of requests | 5 min | Email + SMS |
| p95 latency | > 2500ms | 15 min | Email + SMS |
| Uptime check failure | Either check (edge or service path) failing from ≥2 regions | check-native | Email + SMS |
| Firestore backup failure | Log-based metric `firestore_backup_failures` > 0 | per-event | Email + SMS |

Plus: Error Reporting enabled (`clouderrorreporting.googleapis.com`),
and two counting-only log-based metrics (`voice_turns`,
`agent_text_turns`) with no alert attached — they feed PR-4's
billing-budget thresholds, not paging.

**Uptime checks (two, deliberately redundant):**
- **Edge path:** `https://rvrg.slotsense.chandraailabs.com/health` —
  exercises DNS, cert, Cloud Armor, LB, and backend together.
- **Service path:** the Cloud Run service URL's `/health` directly —
  isolates app health from edge health. One red / one green localizes
  the fault layer immediately.

Both check `GET /health` (`backend/src/sport_slot/health.py:14`) —
pure liveness, no dependency calls — not `/readyz`, which pings
Firestore and would conflate app health with a Firestore blip.

**Thresholds are provisional** (measured-gates principle): set loose
now, tightened once `SLO-LOAD-TEST` (PR-3 follow-on) produces real
traffic distributions. See backlog `ALERT-THRESHOLD-TUNE`.

**Documented residual:** the backup alert detects *failed* backup
operations; it does not detect a schedule that silently never runs.
Absence-detection is `BACKUP-ABSENCE-ALERT` on the backlog, not this PR.
Separately, the `firestore_backup_failures` log filter itself is
defensive/provisional — no real backup failure has occurred yet to
observe the actual Cloud Audit Log shape. **Validate this filter at
the DR drill or the first real failure**, whichever comes first.

## Where alerts go

Two notification channels, both wired to all four alert policies:

- **Email** — `admin@chandraailabs.com`
- **SMS** — Coordinator's number. **The Terraform ships a placeholder
  (`+91XXXXXXXXXX`) — the Coordinator must replace it with the real
  number before apply.** Worker does not invent phone numbers.

## Post-apply steps (Coordinator)

1. **Verify the SMS channel.** Google Cloud Monitoring requires a
   one-time verification code sent to the number after the channel is
   created — check the console (Monitoring → Alerting → Notification
   Channels) and complete verification, or the SMS channel stays
   unverified and alerts silently won't deliver to it.
2. Confirm both uptime checks go green within ~5 minutes of apply.
3. Send a test notification from one alert policy (console "Test
   Notification" button) — confirm **both** email and SMS actually
   arrive, not just that the channel shows as configured.
4. Check Metrics Explorer: trigger one live voice turn in the app and
   confirm `voice_turns` increments.
5. `terraform plan` from `main` post-apply → expect **No changes**.

## Known gap, tracked

`agent_text_turns` and `voice_turns` are built on Cloud Run **platform**
request logs (`run.googleapis.com/requests`), not application logs —
verified against a real `/agent/query` log entry. The application's
own structured logging doesn't give an unconditional per-turn event
for text-agent turns today (`voice.py` logs `voice_request_received`
unconditionally; `agent.py`'s `/query` router and
`orchestrator.run_agent` do not have an equivalent — see backlog
`AGENT-TURN-EVENT` for the follow-up that would add one with
tenant/latency/model dimensions for PR-4's per-tenant cost
attribution). Platform request logs are the interim source and remain
the volume-counter of record until then.
