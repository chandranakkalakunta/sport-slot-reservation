import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

// Mock AuthContext — slug derived from claims; null → query disabled → no firebase call
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ claims: null }),
}));

// No importOriginal — avoids loading real tenantAdminHooks → api.ts → firebase.ts
vi.mock("../../hooks/tenantAdminHooks", () => ({
  useUpdateBranding: vi.fn(),
}));

// Mock api — severs the apiFetch → firebase.ts chain used in the useQuery queryFn
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

import { useUpdateBranding } from "../../hooks/tenantAdminHooks";
import TenantBranding from "./TenantBranding";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TenantBranding />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TenantBranding", () => {
  beforeEach(() => {
    vi.mocked(useUpdateBranding).mockImplementation(
      () => ({ mutateAsync: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useUpdateBranding>,
    );
  });

  it("renders the Branding heading", () => {
    wrap();
    expect(screen.getByRole("heading", { name: "Branding" })).toBeInTheDocument();
  });

  it("renders the Community name label", () => {
    wrap();
    expect(screen.getByLabelText("Community name (optional)")).toBeInTheDocument();
  });

  it("renders the Save branding button", () => {
    wrap();
    expect(screen.getByRole("button", { name: /save branding/i })).toBeInTheDocument();
  });
});
