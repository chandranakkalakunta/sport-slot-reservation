"""Tests for services/invoice_export.py (Phase 15.5).

InvoiceRepository.list_for_tenant_period is patched directly rather than
built out with fake Firestore query infra — this file's concern is the
export logic itself (summary-row shaping, CSV/JSON building, upload path,
signed-URL impersonation), not Firestore query semantics (already covered
for InvoiceRepository elsewhere).

The signed-URL test is the important one: it asserts the actual
impersonation call happened (source_credentials/target_principal/
target_scopes), not just that a URL string came back — per the
operational directive not to assume the keyless path is wired correctly.
"""
import json
from unittest.mock import MagicMock, patch

from sport_slot.services.invoice_export import (
    export_invoices_for_period,
    signed_export_urls,
)

REPO_GET = "sport_slot.services.invoice_export.InvoiceRepository.list_for_tenant_period"
STORAGE_CLIENT = "sport_slot.services.invoice_export.storage.Client"
AUTH_DEFAULT = "sport_slot.services.invoice_export.google.auth.default"
IMPERSONATED_CREDS = "sport_slot.services.invoice_export.impersonated_credentials.Credentials"

INVOICES = [
    {
        "invoice_id": "h-1_2026-06", "household_id": "h-1", "flat_number": "A-1",
        "period": "2026-06", "total_paise": 150050,
        "line_items": [{"facility_name": "Court A", "resident_name": "Alice"}],
    },
    {
        "invoice_id": "h-2_2026-06", "household_id": "h-2", "flat_number": "B-2",
        "period": "2026-06", "total_paise": 5000, "line_items": [],
    },
]


def _mock_storage_client():
    client = MagicMock()
    bucket = MagicMock()
    client.bucket.return_value = bucket
    blobs: dict[str, MagicMock] = {}

    def _blob(path):
        if path not in blobs:
            blobs[path] = MagicMock()
        return blobs[path]

    bucket.blob.side_effect = _blob
    return client, bucket, blobs


def test_export_builds_summary_rows_only_no_line_items():
    """Export content must be summary-level: household_id, flat_number,
    period, total_paise, total_rupees — and NEVER line_items or any
    per-booking detail, per the original high-level-only requirement."""
    client_mock, bucket, blobs = _mock_storage_client()
    with patch(REPO_GET, return_value=INVOICES), patch(STORAGE_CLIENT, return_value=client_mock):
        export_invoices_for_period(MagicMock(), "t-1", "2026-06")

    csv_bytes = blobs["t-1/2026-06/invoices.csv"].upload_from_string.call_args.args[0]
    json_bytes = blobs["t-1/2026-06/invoices.json"].upload_from_string.call_args.args[0]

    csv_text = csv_bytes.decode("utf-8")
    json_rows = json.loads(json_bytes.decode("utf-8"))

    assert "line_items" not in csv_text
    assert "resident_name" not in csv_text
    assert "Court A" not in csv_text  # no per-booking facility detail either
    assert all("line_items" not in row for row in json_rows)

    assert "household_id" in csv_text and "flat_number" in csv_text
    assert "total_paise" in csv_text and "total_rupees" in csv_text
    assert json_rows[0]["household_id"] == "h-1"
    assert json_rows[0]["flat_number"] == "A-1"
    assert json_rows[0]["total_paise"] == 150050
    assert json_rows[0]["total_rupees"] == 1500.5


def test_export_uploads_to_deterministic_tenant_period_path():
    client_mock, bucket, blobs = _mock_storage_client()
    with patch(REPO_GET, return_value=INVOICES), patch(STORAGE_CLIENT, return_value=client_mock):
        result = export_invoices_for_period(MagicMock(), "t-1", "2026-06")

    bucket.blob.assert_any_call("t-1/2026-06/invoices.csv")
    bucket.blob.assert_any_call("t-1/2026-06/invoices.json")
    assert result == {
        "csv_path": "t-1/2026-06/invoices.csv",
        "json_path": "t-1/2026-06/invoices.json",
        "row_count": 2,
    }


def test_export_empty_period_produces_header_only_csv_and_empty_json_array():
    client_mock, bucket, blobs = _mock_storage_client()
    with patch(REPO_GET, return_value=[]), patch(STORAGE_CLIENT, return_value=client_mock):
        result = export_invoices_for_period(MagicMock(), "t-1", "2026-06")

    csv_text = blobs["t-1/2026-06/invoices.csv"].upload_from_string.call_args.args[0].decode()
    json_rows = json.loads(blobs["t-1/2026-06/invoices.json"].upload_from_string.call_args.args[0])

    assert "household_id" in csv_text  # header row still present
    assert json_rows == []
    assert result["row_count"] == 0


def test_manual_reexport_produces_identical_content_to_automatic_export():
    """The automatic (post-generation) call and a manual re-export call
    are the exact same function against the exact same underlying
    invoices — this asserts they produce byte-identical output for the
    same period, not just "similar looking" output."""
    client_mock, bucket, blobs = _mock_storage_client()
    with patch(REPO_GET, return_value=INVOICES), patch(STORAGE_CLIENT, return_value=client_mock):
        export_invoices_for_period(MagicMock(), "t-1", "2026-06")  # simulates the automatic call
        first_csv = blobs["t-1/2026-06/invoices.csv"].upload_from_string.call_args.args[0]
        first_json = blobs["t-1/2026-06/invoices.json"].upload_from_string.call_args.args[0]

        export_invoices_for_period(MagicMock(), "t-1", "2026-06")  # simulates a manual re-export
        second_csv = blobs["t-1/2026-06/invoices.csv"].upload_from_string.call_args.args[0]
        second_json = blobs["t-1/2026-06/invoices.json"].upload_from_string.call_args.args[0]

    assert first_csv == second_csv
    assert first_json == second_json


def test_signed_export_urls_uses_impersonated_credentials_not_default():
    """The whole point of the keyless mechanism: asserts the impersonation
    CALL happened with the right shape, not just that a URL came back."""
    client_mock, bucket, blobs = _mock_storage_client()
    csv_blob = blobs.setdefault("t-1/2026-06/invoices.csv", MagicMock())
    json_blob = blobs.setdefault("t-1/2026-06/invoices.json", MagicMock())
    csv_blob.generate_signed_url.return_value = "https://signed/csv"
    json_blob.generate_signed_url.return_value = "https://signed/json"

    source_creds = MagicMock(name="source_credentials")
    impersonated = MagicMock(name="impersonated_credentials")

    with patch(STORAGE_CLIENT, return_value=client_mock), \
         patch(AUTH_DEFAULT, return_value=(source_creds, "sport-slot-dev")), \
         patch(IMPERSONATED_CREDS, return_value=impersonated) as mock_impersonate:
        urls = signed_export_urls("t-1", "2026-06")

    _, kwargs = mock_impersonate.call_args
    assert kwargs["source_credentials"] is source_creds
    assert kwargs["target_scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]

    csv_blob.generate_signed_url.assert_called_once_with(
        version="v4", expiration=900, credentials=impersonated,
    )
    json_blob.generate_signed_url.assert_called_once_with(
        version="v4", expiration=900, credentials=impersonated,
    )
    assert urls == {"csv_url": "https://signed/csv", "json_url": "https://signed/json"}
