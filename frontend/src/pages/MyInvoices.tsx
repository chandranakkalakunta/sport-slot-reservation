import { AppHeader } from "../components/AppHeader";
import { ListRow } from "../components/ListRow";
import { ResidentNav } from "../components/ResidentNav";
import { useAuth } from "../auth/AuthContext";
import { type Invoice, useMyInvoices } from "../hooks/invoiceHooks";

function toRupees(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

export default function MyInvoices() {
  const { claims } = useAuth();
  const householdId = claims?.household_id as string | undefined;
  const { data, isLoading } = useMyInvoices(!!householdId);
  const invoices = data?.items ?? [];

  return (
    <>
      <AppHeader>
        <ResidentNav />
      </AppHeader>
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Invoices</h1>
        {!householdId && (
          <p className="text-sm text-muted-foreground">
            Your account isn&apos;t linked to a household yet — invoices will appear here
            once it is.
          </p>
        )}
        {householdId && isLoading && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {householdId && !isLoading && invoices.length === 0 && (
          <p className="text-sm text-muted-foreground">No invoices yet.</p>
        )}
        <div className="space-y-2">
          {invoices.map((invoice: Invoice) => (
            <ListRow key={invoice.invoice_id}>
              <p className="font-semibold text-foreground">{invoice.period}</p>
              <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                Total: {toRupees(invoice.total_paise)}
              </p>
              <ul className="mt-2 space-y-1">
                {invoice.line_items.map((item, idx) => (
                  <li
                    key={`${invoice.invoice_id}-${idx}`}
                    className="text-sm text-muted-foreground flex justify-between gap-2"
                  >
                    <span className="truncate">{item.facility_name} · {item.date}</span>
                    <span className="tabular-nums shrink-0">{toRupees(item.price_paise)}</span>
                  </li>
                ))}
              </ul>
            </ListRow>
          ))}
        </div>
      </main>
    </>
  );
}
