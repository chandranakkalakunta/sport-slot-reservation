import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../components/AppHeader", () => ({
  AppHeader: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../hooks/invoiceHooks", () => ({
  useMyInvoices: vi.fn(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../auth/AuthContext";
import * as hooks from "../hooks/invoiceHooks";
import MyInvoices from "./MyInvoices";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const INVOICE = {
  invoice_id: "h-1_2026-06",
  period: "2026-06",
  total_paise: 150050,
  line_items: [
    { booking_id: "b1", facility_id: "f1", facility_name: "Tennis Court", date: "2026-06-05", price_paise: 50000 },
    { booking_id: "b2", facility_id: "f1", facility_name: "Tennis Court", date: "2026-06-12", price_paise: 100050 },
  ],
};

describe("MyInvoices", () => {
  it("shows a distinct message when the account has no household_id", () => {
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: undefined, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByText(/isn't linked to a household yet/i)).toBeInTheDocument();
    // Guard: the hook must be called with enabled=false so no query fires.
    expect(hooks.useMyInvoices).toHaveBeenCalledWith(false);
  });

  it("shows 'No invoices yet' when household_id is present but there are zero invoices", () => {
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByText("No invoices yet.")).toBeInTheDocument();
    expect(hooks.useMyInvoices).toHaveBeenCalledWith(true);
  });

  it("renders an invoice with ₹ totals converted from paise (paise-inclusive)", () => {
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [INVOICE] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByText("2026-06")).toBeInTheDocument();
    expect(screen.getByText("Total: ₹1500.50")).toBeInTheDocument();
    expect(screen.getByText(/Tennis Court · 2026-06-05/)).toBeInTheDocument();
    expect(screen.getByText("₹500.00")).toBeInTheDocument();
    expect(screen.getByText("₹1000.50")).toBeInTheDocument();
  });

  it("renders a whole-rupee total with .00 (no paise remainder)", () => {
    const wholeRupeeInvoice = {
      ...INVOICE,
      invoice_id: "h-1_2026-05",
      period: "2026-05",
      total_paise: 200000,
      line_items: [
        { booking_id: "b3", facility_id: "f1", facility_name: "Badminton Court", date: "2026-05-01", price_paise: 200000 },
      ],
    };
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [wholeRupeeInvoice] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByText("Total: ₹2000.00")).toBeInTheDocument();
  });

  it("renders the shared resident nav including the new Invoices link", () => {
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByRole("link", { name: "Facilities" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "My bookings" })).toHaveAttribute("href", "/bookings");
    expect(screen.getByRole("link", { name: "Invoices" })).toHaveAttribute("href", "/invoices");
  });

  it("shows the booking resident's name per line item in a shared household (15.3 correction)", () => {
    const multiResidentInvoice = {
      ...INVOICE,
      line_items: [
        { ...INVOICE.line_items[0], resident_uid: "u-alice", resident_name: "Alice" },
        { ...INVOICE.line_items[1], resident_uid: "u-bob", resident_name: "Bob" },
      ],
    };
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [multiResidentInvoice] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    expect(screen.getByText(/Tennis Court · 2026-06-05 · Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Tennis Court · 2026-06-12 · Bob/)).toBeInTheDocument();
  });

  it("renders gracefully when resident_name is absent (pre-correction invoices)", () => {
    // INVOICE's fixture line items carry no resident_name at all — mirrors
    // the 2 existing test invoices in Firestore generated before this fix.
    vi.mocked(useAuth).mockReturnValue({
      claims: { role: "resident", household_id: "h-1" },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(hooks.useMyInvoices).mockReturnValue({
      data: { items: [INVOICE] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyInvoices>);

    wrap(<MyInvoices />);

    // No crash, no stray " · undefined" — just facility + date.
    expect(screen.getByText("Tennis Court · 2026-06-05")).toBeInTheDocument();
  });
});
