"""Invoice export to private GCS — CSV + JSON, summary-level only (Phase 15.5).

Fires automatically after each tenant's successful monthly invoice
generation (services/invoicing.py's `_generate_for_tenant`), and is
separately, manually re-triggerable if only the export step (not
generation) needs re-running — e.g. the export files were deleted from
GCS but the invoices themselves are fine. Summary-level only:
household_id, flat_number, period, total_paise AND a rounded total_rupees
convenience field — deliberately NO full line-item detail, per the
original requirement (that was never asked for, and this file is kept
independent of invoicing.py's own GCS-free import surface so as not to
pull storage/auth libraries into a module that otherwise doesn't need
them).

Deterministic path: {tenant_id}/{period}/invoices.{csv,json} — both
formats overwrite in place on every export, so a re-export always
redeposits the CURRENT full set of invoices for that period; no stale or
duplicate files accumulate across repeated runs.

Signed URL generation (keyless architecture): Cloud Run's default
credentials have no private key, so `blob.generate_signed_url` cannot
sign directly with them. This mints short-lived credentials that
IMPERSONATE THE SAME service account Cloud Run already runs as (granted
`roles/iam.serviceAccountTokenCreator` on ITSELF in
terraform/invoice_export.tf) and passes those explicitly — the exact
mechanism already used and working for Firebase Hosting deploy tokens
(terraform/wif_iam.tf's `ci_token_creator_firebase`), just
self-referential this time instead of cross-SA.
"""

import csv
import io
import json

import google.auth
import structlog
from google.auth import impersonated_credentials
from google.cloud import storage

from sport_slot.auth.context import TenantContext
from sport_slot.config import get_settings
from sport_slot.repositories.invoices import InvoiceRepository

log = structlog.get_logger()

_SIGN_URL_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_SIGNED_URL_EXPIRATION_SECONDS = 900  # 15 minutes — short-lived download link
_SUMMARY_FIELDNAMES = ["household_id", "flat_number", "period", "total_paise", "total_rupees"]


def _export_path(tenant_id: str, period: str, ext: str) -> str:
    return f"{tenant_id}/{period}/invoices.{ext}"


def _summary_rows(invoices: list[dict]) -> list[dict]:
    """Summary-level only: household_id, flat_number, period, and the
    total (both raw paise — the authoritative integer — and a rounded
    rupee value for convenience). Deliberately excludes line_items."""
    return [
        {
            "household_id": inv.get("household_id"),
            "flat_number": inv.get("flat_number"),
            "period": inv.get("period"),
            "total_paise": inv.get("total_paise"),
            "total_rupees": round((inv.get("total_paise") or 0) / 100, 2),
        }
        for inv in invoices
    ]


def _build_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_SUMMARY_FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _build_json(rows: list[dict]) -> bytes:
    return json.dumps(rows, indent=2).encode("utf-8")


def export_invoices_for_period(client, tenant_id: str, period: str) -> dict:
    """Build and upload BOTH a CSV and a JSON summary of every invoice this
    tenant has for `period`, to the private export bucket — overwriting
    any prior export at the same deterministic path. Returns
    {"csv_path", "json_path", "row_count"}. A period with zero invoices
    still uploads a header-only CSV and an empty JSON array — not an
    error, just nothing to report.
    """
    ctx = TenantContext(
        uid="system:invoice-export", tenant_id=tenant_id, tenant_slug=None,
        role="system", household_id=None,
    )
    invoices = InvoiceRepository(ctx, client).list_for_tenant_period(period)
    rows = _summary_rows(invoices)

    settings = get_settings()
    storage_client = storage.Client(project=settings.gcp_project)
    bucket = storage_client.bucket(settings.invoice_export_bucket)

    csv_path = _export_path(tenant_id, period, "csv")
    json_path = _export_path(tenant_id, period, "json")

    bucket.blob(csv_path).upload_from_string(_build_csv(rows), content_type="text/csv")
    bucket.blob(json_path).upload_from_string(_build_json(rows), content_type="application/json")

    log.info("invoice_export_uploaded", tenant_id=tenant_id, period=period,
              row_count=len(rows), csv_path=csv_path, json_path=json_path)
    return {"csv_path": csv_path, "json_path": json_path, "row_count": len(rows)}


def _impersonated_credentials():
    """Mint short-lived credentials impersonating THIS SAME service
    account — the only way to sign a GCS URL under Cloud Run's keyless
    architecture. Requires roles/iam.serviceAccountTokenCreator granted
    to the SA on itself (terraform/invoice_export.tf); without that
    grant this raises a permission-denied error when the signed URL is
    actually requested, not a private-key error — confirming the keyless
    path is wired correctly rather than silently falling back to one.
    """
    settings = get_settings()
    source_credentials, _ = google.auth.default()
    return impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=settings.cloud_run_sa_email,
        target_scopes=_SIGN_URL_SCOPES,
        lifetime=_SIGNED_URL_EXPIRATION_SECONDS,
    )


def signed_export_urls(tenant_id: str, period: str) -> dict:
    """Short-lived (15 min) signed download URLs for the tenant's CSV +
    JSON export files for `period`. Always uses impersonated credentials
    — never Cloud Run's default credentials directly, which have no
    private key to sign with.
    """
    settings = get_settings()
    storage_client = storage.Client(project=settings.gcp_project)
    bucket = storage_client.bucket(settings.invoice_export_bucket)
    creds = _impersonated_credentials()

    csv_blob = bucket.blob(_export_path(tenant_id, period, "csv"))
    json_blob = bucket.blob(_export_path(tenant_id, period, "json"))

    return {
        "csv_url": csv_blob.generate_signed_url(
            version="v4", expiration=_SIGNED_URL_EXPIRATION_SECONDS, credentials=creds,
        ),
        "json_url": json_blob.generate_signed_url(
            version="v4", expiration=_SIGNED_URL_EXPIRATION_SECONDS, credentials=creds,
        ),
    }
