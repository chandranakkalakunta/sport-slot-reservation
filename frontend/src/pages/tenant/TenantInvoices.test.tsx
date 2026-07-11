import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useTenantLatestInvoices: vi.fn(),
  useTenantInvoiceHistory: vi.fn(),
  useTenantInvoicePreview: vi.fn(),
}));

import {
  useTenantInvoiceHistory,
  useTenantInvoicePreview,
  useTenantLatestInvoices,
} from "../../hooks/tenantAdminHooks";
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

  describe("selecting a flat's row (15.4c)", () => {
    const HISTORY_ITEM = {
      invoice_id: "h-1_2026-05", household_id: "h-1", flat_number: "A-1",
      period: "2026-05", total_paise: 100000, line_items: [],
    };
    const PREVIEW = {
      household_id: "h-1", period: "2026-07", period_start: "2026-07-01",
      period_end: "2026-07-11", flat_number: "A-1", total_paise: 4200,
      line_items: [
        { booking_id: "b1", facility_id: "f1", facility_name: "Tennis Court",
          date: "2026-07-05", price_paise: 4200, resident_name: "Alice" },
      ],
      preview: true as const,
    };

    beforeEach(() => {
      vi.mocked(useTenantLatestInvoices).mockReturnValue({
        data: { items: INVOICES }, isLoading: false,
      } as unknown as ReturnType<typeof useTenantLatestInvoices>);
      vi.mocked(useTenantInvoiceHistory).mockReturnValue({
        data: { items: [HISTORY_ITEM] }, isLoading: false,
      } as unknown as ReturnType<typeof useTenantInvoiceHistory>);
      vi.mocked(useTenantInvoicePreview).mockReturnValue({
        data: PREVIEW, isLoading: false,
      } as unknown as ReturnType<typeof useTenantInvoicePreview>);
    });

    it("does not fetch history/preview until a row is selected", () => {
      renderPage();

      expect(useTenantInvoiceHistory).not.toHaveBeenCalled();
      expect(useTenantInvoicePreview).not.toHaveBeenCalled();
    });

    it("reveals history and a clearly-labeled preview when a row is clicked", async () => {
      const user = userEvent.setup();
      renderPage();

      expect(screen.queryByText("Preview — not yet invoiced")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /A-1/ }));

      // Preview — visually distinguished with its own explicit label.
      expect(screen.getByText("Preview — not yet invoiced")).toBeInTheDocument();
      expect(screen.getByText("2026-07 (in progress) · ₹42.00")).toBeInTheDocument();
      expect(screen.getByText(/Tennis Court · 2026-07-05 · Alice/)).toBeInTheDocument();

      // History — a real, generated invoice, rendered separately from the preview.
      expect(screen.getByText("Recent invoices")).toBeInTheDocument();
      expect(screen.getByText("2026-05 · ₹1000.00")).toBeInTheDocument();
    });

    it("collapses the detail when the same row is clicked again", async () => {
      const user = userEvent.setup();
      renderPage();

      const row = screen.getByRole("button", { name: /A-1/ });
      await user.click(row);
      expect(screen.getByText("Preview — not yet invoiced")).toBeInTheDocument();

      await user.click(row);
      expect(screen.queryByText("Preview — not yet invoiced")).not.toBeInTheDocument();
    });
  });
});
