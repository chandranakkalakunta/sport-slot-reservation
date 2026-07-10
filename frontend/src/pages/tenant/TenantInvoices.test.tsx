import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useTenantLatestInvoices: vi.fn(),
}));

import { useTenantLatestInvoices } from "../../hooks/tenantAdminHooks";
import TenantInvoices from "./TenantInvoices";

const INVOICES = [
  { invoice_id: "h-1_2026-06", household_id: "h-1", flat_number: "A-1", period: "2026-06", total_paise: 150000 },
  { invoice_id: "h-2_2026-06", household_id: "h-2", flat_number: "B-2", period: "2026-06", total_paise: 5050 },
];

function renderPage() {
  return render(<MemoryRouter><TenantInvoices /></MemoryRouter>);
}

describe("TenantInvoices", () => {
  it("lists the latest invoice per flat with ₹ total", () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: { items: INVOICES }, isLoading: false,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);

    renderPage();

    expect(screen.getByText("A-1")).toBeInTheDocument();
    expect(screen.getByText("2026-06 · ₹1500.00")).toBeInTheDocument();
    expect(screen.getByText("B-2")).toBeInTheDocument();
    expect(screen.getByText("2026-06 · ₹50.50")).toBeInTheDocument();
  });

  it("shows 'No invoices yet' for a tenant with zero invoices, not an error", () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);

    renderPage();

    expect(screen.getByText("No invoices yet.")).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: undefined, isLoading: true,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);

    renderPage();

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  // NOTE: search is client-side only — filters the already-fetched list.
  it("search filters by flat_number substring", async () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: { items: INVOICES }, isLoading: false,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByText("A-1")).toBeInTheDocument();
    expect(screen.getByText("B-2")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/search invoices by flat/i), "a-1");

    expect(screen.getByText("A-1")).toBeInTheDocument();
    expect(screen.queryByText("B-2")).not.toBeInTheDocument();
  });

  it("search shows empty-state message when no flats match", async () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: { items: INVOICES }, isLoading: false,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/search invoices by flat/i), "zzz");

    expect(screen.getByText(/no flats match/i)).toBeInTheDocument();
  });

  it("renders the Dashboard back-link", () => {
    vi.mocked(useTenantLatestInvoices).mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof useTenantLatestInvoices>);

    renderPage();

    expect(screen.getByRole("link", { name: /Dashboard/ })).toHaveAttribute("href", "/tenant");
  });
});
