import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

// No importOriginal — avoids loading real tenantAdminHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../../hooks/tenantAdminHooks", () => ({
  useUpdatePolicies: vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  ApiClientError: class extends Error {
    code: string;
    status: number;
    constructor(e: { code: string; message: string; status: number }) {
      super(e.message);
      this.code = e.code;
      this.status = e.status;
    }
  },
  apiFetch: vi.fn(),
}));

import { useUpdatePolicies } from "../../hooks/tenantAdminHooks";
import TenantPolicies from "./TenantPolicies";

function renderPage() {
  return render(<MemoryRouter><TenantPolicies /></MemoryRouter>);
}

describe("TenantPolicies", () => {
  beforeEach(() => {
    vi.mocked(useUpdatePolicies).mockImplementation(
      () => ({ mutateAsync: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useUpdatePolicies>,
    );
  });

  it("renders the Booking Policies heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Booking Policies" })).toBeInTheDocument();
  });

  it("renders the Save policies button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /save policies/i })).toBeInTheDocument();
  });

  it("shows Saving… on the button when pending", () => {
    vi.mocked(useUpdatePolicies).mockImplementation(
      () => ({ mutateAsync: vi.fn(), isPending: true }) as unknown as ReturnType<typeof useUpdatePolicies>,
    );
    renderPage();
    expect(screen.getByRole("button", { name: /saving/i })).toBeInTheDocument();
  });
});
