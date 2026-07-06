import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

// No importOriginal — avoids loading real adminHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../../hooks/adminHooks", () => ({
  useTenants: vi.fn(),
  useDeleteTenantPermanently: vi.fn(),
}));

import { useTenants, useDeleteTenantPermanently } from "../../hooks/adminHooks";
import TenantList from "./TenantList";

const TENANT = {
  tenant_id: "t-1", slug: "oakwood", display_name: "Oakwood Residency",
  name: "Oakwood", active: true,
};

function renderPage() {
  return render(<MemoryRouter><TenantList /></MemoryRouter>);
}

describe("TenantList", () => {
  beforeEach(() => {
    vi.mocked(useTenants).mockReturnValue({
      data: { items: [TENANT] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useTenants>);
    vi.mocked(useDeleteTenantPermanently).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useDeleteTenantPermanently>);
  });

  it("renders Platform Admin and Tenants headings", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Platform Admin" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tenants" })).toBeInTheDocument();
  });

  it("renders the + New tenant link with correct href", () => {
    renderPage();
    expect(screen.getByRole("link", { name: /new tenant/i })).toHaveAttribute(
      "href",
      "/admin/tenants/new",
    );
  });

  it("renders a tenant row from mock data", () => {
    renderPage();
    expect(screen.getByText("Oakwood Residency")).toBeInTheDocument();
    expect(screen.getByText(/oakwood/)).toBeInTheDocument();
  });

  it("shows loading state", () => {
    vi.mocked(useTenants).mockReturnValue({
      data: undefined, isLoading: true, error: null,
    } as unknown as ReturnType<typeof useTenants>);
    renderPage();
    expect(screen.getByText("Loading tenants…")).toBeInTheDocument();
  });

  it("shows error state", () => {
    vi.mocked(useTenants).mockReturnValue({
      data: undefined, isLoading: false, error: new Error("network"),
    } as unknown as ReturnType<typeof useTenants>);
    renderPage();
    expect(screen.getByText("Couldn't load tenants.")).toBeInTheDocument();
  });

  it("shows empty state when no tenants", () => {
    vi.mocked(useTenants).mockReturnValue({
      data: { items: [] }, isLoading: false, error: null,
    } as unknown as ReturnType<typeof useTenants>);
    renderPage();
    expect(screen.getByText("No tenants yet.")).toBeInTheDocument();
  });

  // ── Phase 13.4: tenant permanent delete ──────────────────────────────────

  it("(d) renders a Delete button for each tenant row", () => {
    // RED: before Phase 13.4 no Delete button exists in TenantList.
    renderPage();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });

  it("(d) Delete button opens a confirm dialog requiring the tenant's slug", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /delete/i }));
    // The ConfirmDialog renders a textbox for the confirmationPhrase.
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    // The phrase label shows the actual tenant slug, not a generic literal.
    expect(screen.getByText(/Type oakwood to confirm/i)).toBeInTheDocument();
  });

  it("(d) confirm button disabled for non-matching input including another tenant's slug", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /delete/i }));
    const confirmBtn = screen.getByRole("button", { name: /confirm/i });
    // Non-empty but wrong slug must not enable the button.
    await user.type(screen.getByRole("textbox"), "different-tenant");
    expect(confirmBtn).toBeDisabled();
  });

  it("(d) confirm button enabled only on exact matching tenant slug", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /delete/i }));
    await user.type(screen.getByRole("textbox"), "oakwood");
    expect(screen.getByRole("button", { name: /confirm/i })).not.toBeDisabled();
  });

  it("(d) confirming deletion calls the mutation with the correct tenant_id", async () => {
    const mutate = vi.fn();
    vi.mocked(useDeleteTenantPermanently).mockReturnValue({
      mutate, isPending: false,
    } as unknown as ReturnType<typeof useDeleteTenantPermanently>);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /delete/i }));
    await user.type(screen.getByRole("textbox"), "oakwood");
    await user.click(screen.getByRole("button", { name: /confirm/i }));
    expect(mutate).toHaveBeenCalledWith("t-1");
  });
});
