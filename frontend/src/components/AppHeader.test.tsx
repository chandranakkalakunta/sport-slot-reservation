import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppHeader } from "./AppHeader";

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "admin@demo.com" },
    claims: { role: "tenant_admin" },
    signOut: vi.fn(),
  }),
}));

vi.mock("../lib/branding", () => ({
  getLastBranding: () => ({
    slug: "demo",
    brand_name: "Green Park",
    brand_primary_color: "#1a4d8f",
    brand_secondary_color: "#0f7b6c",
    brand_logo_url: null,
  }),
}));

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("AppHeader", () => {
  it("renders user email and role label", () => {
    wrap(<AppHeader />);
    expect(screen.getByText(/admin@demo\.com · Tenant admin/)).toBeInTheDocument();
  });

  it("renders brand name as a navigation link", () => {
    wrap(<AppHeader />);
    expect(screen.getByRole("link", { name: "Green Park" })).toBeInTheDocument();
  });

  it("renders children in the header slot", () => {
    wrap(<AppHeader><span>My bookings</span></AppHeader>);
    expect(screen.getByText("My bookings")).toBeInTheDocument();
  });
});
