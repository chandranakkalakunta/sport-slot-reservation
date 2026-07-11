import { useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  useInvoiceExportDownloadUrls,
  useReExportInvoices,
  useRegenerateInvoices,
  useTenantInvoiceHistory,
  useTenantInvoicePreview,
  useTenantLatestInvoices,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import type { InvoiceLineItem } from "../../hooks/invoiceHooks";

function toRupees(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

function AdminActions() {
  const [period, setPeriod] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const regenerate = useRegenerateInvoices();
  const reExport = useReExportInvoices();
  const downloadUrls = useInvoiceExportDownloadUrls();

  const periodArg = period.trim() || undefined;

  async function handleRegenerate() {
    setError(null); setMessage(null);
    try {
      const summary = await regenerate.mutateAsync(periodArg);
      const failedNote = summary.households_failed.length
        ? `, ${summary.households_failed.length} failed` : "";
      setMessage(
        `Regenerated ${summary.period}: ${summary.households_invoiced} invoiced, `
        + `${summary.households_skipped} skipped${failedNote}.`,
      );
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : "Regeneration failed.");
    }
  }

  async function handleReExport() {
    setError(null); setMessage(null);
    try {
      const result = await reExport.mutateAsync(periodArg);
      setMessage(`Exported ${result.row_count} invoice(s).`);
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : "Export failed.");
    }
  }

  async function handleDownload(kind: "csv" | "json") {
    setError(null); setMessage(null);
    try {
      const urls = await downloadUrls.mutateAsync(periodArg);
      window.open(kind === "csv" ? urls.csv_url : urls.json_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : "Could not get a download link.");
    }
  }

  return (
    <section className="rounded-lg border bg-card p-3 space-y-3">
      <p className="text-sm font-semibold text-foreground">Admin actions</p>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Period (YYYY-MM, optional)"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="max-w-[180px]"
          aria-label="Period for admin actions"
        />
        <Button
          variant="outline" size="sm"
          onClick={handleRegenerate} disabled={regenerate.isPending}
        >
          {regenerate.isPending ? "Regenerating…" : "Regenerate"}
        </Button>
        <Button
          variant="outline" size="sm"
          onClick={handleReExport} disabled={reExport.isPending}
        >
          {reExport.isPending ? "Exporting…" : "Re-export"}
        </Button>
        <Button
          variant="outline" size="sm"
          onClick={() => handleDownload("csv")} disabled={downloadUrls.isPending}
        >
          Download CSV
        </Button>
        <Button
          variant="outline" size="sm"
          onClick={() => handleDownload("json")} disabled={downloadUrls.isPending}
        >
          Download JSON
        </Button>
      </div>
      {message && <p className="text-sm text-success">{message}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  );
}

function LineItemList({ items }: { items: InvoiceLineItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">No bookings.</p>;
  }
  return (
    <ul className="space-y-0.5">
      {items.map((item, idx) => (
        <li
          key={`${item.booking_id}-${idx}`}
          className="text-sm text-muted-foreground flex justify-between gap-2"
        >
          <span className="truncate">
            {item.facility_name} · {item.date}
            {item.resident_name && <> · {item.resident_name}</>}
          </span>
          <span className="tabular-nums shrink-0">{toRupees(item.price_paise)}</span>
        </li>
      ))}
    </ul>
  );
}

function HouseholdDetail({ householdId }: { householdId: string }) {
  const { data: history, isLoading: historyLoading } = useTenantInvoiceHistory(householdId);
  const { data: preview, isLoading: previewLoading } = useTenantInvoicePreview(householdId);

  return (
    <div className="rounded-lg border border-dashed bg-muted/30 p-3 ml-2 space-y-4">
      {/* Live, unpersisted — must never be mistaken for a real invoice. */}
      <section className="space-y-1">
        <Badge variant="secondary">Preview — not yet invoiced</Badge>
        {previewLoading && <p className="text-sm text-muted-foreground">Loading preview…</p>}
        {preview && (
          <>
            <p className="text-sm font-medium text-foreground tabular-nums">
              {preview.period} (in progress) · {toRupees(preview.total_paise)}
            </p>
            <LineItemList items={preview.line_items} />
          </>
        )}
      </section>

      <section className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Recent invoices
        </p>
        {historyLoading && <p className="text-sm text-muted-foreground">Loading history…</p>}
        {history && history.items.length === 0 && (
          <p className="text-sm text-muted-foreground">No generated invoices yet.</p>
        )}
        <div className="space-y-2">
          {history?.items.map((inv) => (
            <div key={inv.invoice_id} className="space-y-0.5">
              <p className="text-sm font-medium text-foreground tabular-nums">
                {inv.period} · {toRupees(inv.total_paise)}
              </p>
              <LineItemList items={inv.line_items} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function TenantInvoices() {
  const { data, isLoading } = useTenantLatestInvoices();
  const [search, setSearch] = useState("");
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string | null>(null);

  const invoices = data?.items ?? [];

  const filtered = invoices.filter((inv) => {
    if (!search) return true;
    return (inv.flat_number ?? "").toLowerCase().includes(search.toLowerCase());
  });

  function toggleSelect(householdId: string) {
    setSelectedHouseholdId((current) => (current === householdId ? null : householdId));
  }

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        <Link to="/tenant" className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Invoices</h1>

        <AdminActions />

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

        {/* Search — client-side filter of the current page only */}
        {!isLoading && invoices.length > 0 && (
          <Input
            placeholder="Search by flat number…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
            aria-label="Search invoices by flat"
          />
        )}

        {invoices.length === 0 && !isLoading && (
          <p className="text-sm text-muted-foreground">No invoices yet.</p>
        )}
        {invoices.length > 0 && filtered.length === 0 && (
          <p className="text-sm text-muted-foreground">No flats match "{search}".</p>
        )}

        <div className="space-y-2">
          {filtered.map((inv) => (
            <div key={inv.household_id} className="space-y-2">
              <button
                type="button"
                onClick={() => toggleSelect(inv.household_id)}
                aria-expanded={selectedHouseholdId === inv.household_id}
                className="w-full text-left rounded-lg border bg-card p-2 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 hover:bg-accent transition-colors"
              >
                <p className="font-semibold text-foreground">
                  {inv.flat_number ?? "Unknown flat"}
                </p>
                <p className="text-sm text-muted-foreground tabular-nums">
                  {inv.period} · {toRupees(inv.total_paise)}
                </p>
              </button>

              {selectedHouseholdId === inv.household_id && (
                <HouseholdDetail householdId={inv.household_id} />
              )}
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
