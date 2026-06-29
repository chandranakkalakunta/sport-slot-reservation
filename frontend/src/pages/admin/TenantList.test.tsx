import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

// No importOriginal — avoids loading real adminHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../../hooks/adminHooks", () => ({
  useTenants: vi.fn(),
}));

import { useTenants } from "../../hooks/adminHooks";
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
});
