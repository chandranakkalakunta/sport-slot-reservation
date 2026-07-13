# Learnings — Voice I/O Live Debugging (2026-07-13)

**Context:** The voice feature (sub-phases 1a–2) was fully built, merged, and
passing all CI gates. First live test revealed it did not work. Getting from
"totally blank" to a working voice booking took a long session and surfaced
**six distinct failures — none in the application logic we wrote, all in
config, environment, permissions, or observability.** Every one was invisible
to the test suite. This document records them so the pattern is not re-learned
the hard way.

**Meta-lesson (the headline):** *A green test suite proves the code is correct
in a mocked environment. It says almost nothing about whether the deployed
system works.* Every failure below passed every test. The fixes were all
outside the code under test — and several were invisible until observability
itself was repaired.

---

## The six failures, in the order they surfaced

### 1. Blank screen — Firebase key missing in the CI test environment
- **Symptom:** After deploy, the app rendered a blank white screen; a new test
  (`Assistant.test.tsx`) failed CI with `auth/invalid-api-key`.
- **Cause:** The new test rendered a Firebase-importing component without
  mocking `lib/firebase.ts`. Every *other* test mocks it; this one didn't.
  `getAuth()` runs at import, and CI has no `VITE_FIREBASE_API_KEY`, so it threw.
- **Fix:** Add `vi.mock("../lib/firebase", …)` — match the existing convention.
- **Lesson:** *Frontend tests "pass locally" because the dev machine has a
  `.env` with real keys. CI does not.* Any test rendering a component that
  initializes an external SDK at import must mock that SDK, or it will pass
  locally and fail in CI.

### 2. `/agent/voice` 404 → served `index.html` — env var never set
- **Symptom:** Voice request returned `200 OK` but the body was `index.html`
  (empty bubbles). Direct backend URL 404'd.
- **Cause:** The endpoint is feature-flagged: flag off → route returns 404. The
  LB's SPA catch-all then rewrote that 404 into `index.html`. The flag
  (`SPORTSLOT_VOICE_ENABLED`) was simply never set on the service.
- **Fix:** Set the env var on Cloud Run.
- **Lesson:** *A `200` is not success — check the `Content-Type` and `Server`
  headers.* GCS-served `index.html` carries `Server: UploadServer` and
  `X-Goog-*` headers; that fingerprint means the request never reached the app.

### 3. Wrong env var name — `VOICE_ENABLED` vs `SPORTSLOT_VOICE_ENABLED`
- **Symptom:** After setting `VOICE_ENABLED=true`, still 404.
- **Cause:** The app uses pydantic `BaseSettings` with env prefix `SPORTSLOT_`,
  so the real var name is `SPORTSLOT_VOICE_ENABLED`. The bare `VOICE_ENABLED`
  was ignored; the setting fell back to its `False` default.
- **Fix:** Set the correctly-prefixed name; remove the wrong one.
- **Lesson:** *The env var name is a config contract that lived only in a
  docstring.* Config-var names must be documented operationally (a runbook),
  not discovered by grepping source. See also: the settings prefix applies to
  every var.

### 4. Direct Cloud Run URL 404s everything — an invalid diagnostic
- **Symptom:** `curl` to the `…run.app` URL returned 404 for `/agent/voice` —
  taken (wrongly) as proof the route was missing.
- **Cause:** The direct `…run.app` URL 404s *every* path this way, including
  `/agent/query` which works fine in the browser. The valid entry point is the
  load balancer (`rvrg.slotsense…`), not the raw Cloud Run URL.
- **Fix:** None needed — the probe itself was invalid.
- **Lesson:** *Before trusting a diagnostic, validate it against a known-good
  case.* One `curl` of the working `/agent/query` would have shown the same
  404 and exposed the probe as meaningless. Always test your test.

### 5. Flag reset to default on every deploy
- **Symptom:** After deploying the instrumented build, voice 404'd again despite
  the flag having been set earlier.
- **Cause:** The flag was set imperatively via `gcloud run update` on one
  revision. A new CI deploy builds a fresh revision from the pipeline's own env
  config — which doesn't include the flag — so it reverted to default (off).
- **Fix (temporary):** Re-set the flag after deploy.
- **Fix (permanent, backlog VOICE-FLAG-PERSIST):** Bake the flag into the deploy
  config (deploy script / CI env / Terraform).
- **Lesson:** *Imperative config on a Cloud Run revision does not survive the
  next deploy.* Anything set by hand via `gcloud run update` is ephemeral unless
  the deploy pipeline also sets it.

### 6. Structured logs invisible in the viewer — `event` vs `message`
- **Symptom:** The app's `log.info`/`log.warning` lines rendered as *blank
  lines* in `gcloud run services logs read` and the Logs Explorer summary. This
  made the real bug (below) undiagnosable and caused repeated misreading of
  "no log line" as "code didn't run."
- **Cause:** structlog writes the event text into a field named `event`, but
  Cloud Logging builds each entry's one-line summary from a top-level `message`
  field. The full payload was in `jsonPayload` all along — just invisible in
  every summary view.
- **Fix (permanent):** Add `structlog.processors.EventRenamer("message")` to the
  processor chain. This fixed *all* structured logging in prod, not just voice.
- **Also:** `gcloud run services logs read` shows a simplified view that omits
  `jsonPayload`. `gcloud logging read '…' --format="value(jsonPayload.message)"`
  shows the truth.
- **Lesson:** *"No log line" does not mean "code didn't run" until you've
  confirmed the logging pipeline itself renders.* When instrumentation you just
  added to see a problem also doesn't appear, suspect the observability layer
  before the code.

---

## The actual root-cause bug (what all the above was hiding)

Once logging was visible, one line ended the search:

> `403 Permission 'speech.recognizers.recognize' denied on resource
> 'projects/…/locations/asia-southeast1/recognizers/_'` — `IAM_PERMISSION_DENIED`

- **Cause:** The Cloud Run runtime service account
  (`sa-cloud-run@sport-slot-dev.iam.gserviceaccount.com`) lacked permission to
  call Speech-to-Text. Local testing worked because the developer's own ADC
  *had* the permission; the deployed service account did not.
- **Fix:** Grant `roles/speech.client` (includes `speech.recognizers.recognize`)
  to the runtime SA. Project-level, propagates in under a minute, no redeploy.
- **Fix (permanent, backlog VOICE-IAM-TF):** Codify the grant in Terraform,
  alongside the other IAM grants — it is currently imperative and will drift on
  infra rebuild.
- **Why no test caught it:** `stt.py`'s unit tests mock the Speech client, so a
  real IAM 403 can never surface there. The error was also swallowed: the
  pipeline catches `SttError` and degrades to "Sorry, I didn't catch that,"
  making a hard permission failure look like "heard nothing."

---

## Cross-cutting patterns (candidates for protocol v3.8)

1. **Mocked integration points hide real-world failures.** Anywhere a test
   mocks an external client (Firebase, Speech, GCS, Vertex), the real
   integration can still fail on IAM, quota, region, env, or auth — and *only*
   a deployed smoke test reveals it. Treat "the integration is mocked in tests"
   as "this integration is unverified until run live."
2. **Config/permission does not travel with code.** Env vars reset on deploy;
   IAM grants live in the live policy, not source; both must be codified
   (deploy config / Terraform) or they silently regress. "It worked once" ≠ "it
   is configured."
3. **Observability is a prerequisite, not a nicety.** Half this session was
   spent blind because structured logs didn't render. Fix logging *first*; you
   cannot debug what you cannot see, and absence of a log line is not evidence.
4. **Validate the diagnostic before trusting it.** A probe that 404s the
   known-good route too is measuring nothing. Test your test against a
   known-good case first.
5. **`200 OK` is not success.** Check content-type, server headers, and the body
   shape — an SPA fallback, a cache, or an error page can all return 200.
6. **Swallowed errors masquerade as empty results.** A fail-safe branch
   ("didn't catch that") that catches *all* exceptions hides hard failures as
   soft ones. Log the full exception at the catch site (this is exactly what
   made the 403 finally visible once logging worked).

## Process note

The turning point was **stopping live hot-patching and handing diagnosis to the
Worker** with a strict "instrument, do not fix" mandate. The Worker found the
real cause of the blank logs (`event`→`message`) by measuring, which then
exposed the 403. Earlier, repeated guess-and-check at the terminal produced
several confidently-wrong hypotheses (stale image, LB routing, size-cap
double-read, format-decode) and cost the most time. Measure-first, one change
at a time, diagnostic separated from fix — the protocol's core discipline — is
what closed it.
