import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

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

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.mode;
  document.documentElement.style.removeProperty("--color-primary");
});

afterEach(() => {
  vi.restoreAllMocks();
  delete document.documentElement.dataset.mode;
  document.documentElement.style.removeProperty("--color-primary");
});

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("AppHeader — existing contract", () => {
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

describe("AppHeader — dark mode toggle", () => {
  it("renders the dark-mode toggle button", () => {
    wrap(<AppHeader />);
    expect(
      screen.getByRole("button", { name: "Switch to dark mode" })
    ).toBeInTheDocument();
  });

  it("clicking toggle sets data-mode=dark and updates aria-label", async () => {
    const user = userEvent.setup();
    wrap(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));

    expect(document.documentElement.dataset.mode).toBe("dark");
    expect(
      screen.getByRole("button", { name: "Switch to light mode" })
    ).toBeInTheDocument();
  });

  it("clicking toggle twice returns to light mode", async () => {
    const user = userEvent.setup();
    wrap(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));

    expect(document.documentElement.dataset.mode).toBeUndefined();
  });
});

describe("AppHeader — dark mode × branding coexistence", () => {
  it("dark-mode toggle does not clobber runtime --color-primary override", async () => {
    const user = userEvent.setup();
    // Simulate branding.ts runtime override
    document.documentElement.style.setProperty("--color-primary", "#d6336c");

    wrap(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(document.documentElement.dataset.mode).toBe("dark");
    expect(
      document.documentElement.style.getPropertyValue("--color-primary")
    ).toBe("#d6336c");

    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(document.documentElement.dataset.mode).toBeUndefined();
    expect(
      document.documentElement.style.getPropertyValue("--color-primary")
    ).toBe("#d6336c");
  });
});

describe("AppHeader — mobile menu", () => {
  it("hamburger button is present", () => {
    wrap(<AppHeader />);
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });

  it("mobile navigation is hidden by default", () => {
    wrap(<AppHeader />);
    expect(
      screen.queryByRole("navigation", { name: "Mobile navigation" })
    ).not.toBeInTheDocument();
  });

  it("clicking hamburger opens mobile nav with Account and Sign out", async () => {
    const user = userEvent.setup();
    wrap(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Open menu" }));

    const mobileNav = screen.getByRole("navigation", { name: "Mobile navigation" });
    expect(mobileNav).toBeInTheDocument();
    expect(within(mobileNav).getByRole("link", { name: "Account" })).toBeInTheDocument();
    expect(within(mobileNav).getByRole("button", { name: /Sign out/ })).toBeInTheDocument();
  });

  it("mobile nav reveals caller-supplied children", async () => {
    const user = userEvent.setup();
    wrap(<AppHeader><span>My bookings</span></AppHeader>);

    await user.click(screen.getByRole("button", { name: "Open menu" }));

    const mobileNav = screen.getByRole("navigation", { name: "Mobile navigation" });
    expect(within(mobileNav).getByText("My bookings")).toBeInTheDocument();
  });

  it("clicking hamburger again closes the mobile nav", async () => {
    const user = userEvent.setup();
    wrap(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(
      screen.getByRole("navigation", { name: "Mobile navigation" })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close menu" }));
    expect(
      screen.queryByRole("navigation", { name: "Mobile navigation" })
    ).not.toBeInTheDocument();
  });
});
