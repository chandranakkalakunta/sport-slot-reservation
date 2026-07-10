import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

import TenantDashboard from "./TenantDashboard";

function renderPage() {
  return render(<MemoryRouter><TenantDashboard /></MemoryRouter>);
}

describe("TenantDashboard", () => {
  it("renders the Tenant Admin heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Tenant Admin" })).toBeInTheDocument();
  });

  it("renders navigation links to each admin section", () => {
    renderPage();
    expect(screen.getByRole("link", { name: /Facilities/ })).toHaveAttribute("href", "/tenant/facilities");
    expect(screen.getByRole("link", { name: /Branding/ })).toHaveAttribute("href", "/tenant/branding");
    expect(screen.getByRole("link", { name: /Policies/ })).toHaveAttribute("href", "/tenant/policies");
    expect(screen.getByRole("link", { name: /Residents/ })).toHaveAttribute("href", "/tenant/users");
    expect(screen.getByRole("link", { name: /Invoices/ })).toHaveAttribute("href", "/tenant/invoices");
  });
});
