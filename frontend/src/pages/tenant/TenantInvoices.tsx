import { useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Input } from "../../components/ui/input";
import { useTenantLatestInvoices } from "../../hooks/tenantAdminHooks";

function toRupees(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

export default function TenantInvoices() {
  const { data, isLoading } = useTenantLatestInvoices();
  const [search, setSearch] = useState("");

  const invoices = data?.items ?? [];

  const filtered = invoices.filter((inv) => {
    if (!search) return true;
    return (inv.flat_number ?? "").toLowerCase().includes(search.toLowerCase());
  });

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        <Link to="/tenant" className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Invoices</h1>

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
            <div
              key={inv.household_id}
              className="rounded-lg border bg-card p-2 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
            >
              <p className="font-semibold text-foreground">
                {inv.flat_number ?? "Unknown flat"}
              </p>
              <p className="text-sm text-muted-foreground tabular-nums">
                {inv.period} · {toRupees(inv.total_paise)}
              </p>
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
