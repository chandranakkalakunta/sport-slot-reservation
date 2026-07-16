# Voice STT — Speech-to-Text access (ADR-0036, ADR-0037)
#
# The Cloud Run runtime SA (sa-cloud-run) calls Speech-to-Text
# (speech.recognizers.recognize) to transcribe resident voice turns
# (POST /agent/voice). This role was granted IMPERATIVELY via
# `gcloud projects add-iam-policy-binding` on 2026-07-13 to fix a live
# 403 during voice debugging (see docs/retrospectives/
# voice-io-debugging-2026-07-13.md). Codifying it here so it replicates
# to Test/Prod on apply instead of drifting/vanishing on infra rebuild.

resource "google_project_iam_member" "cloud_run_speech_client" {
  project = var.project_id
  role    = "roles/speech.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}
