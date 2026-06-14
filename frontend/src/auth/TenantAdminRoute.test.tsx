import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TenantAdminRoute } from "./TenantAdminRoute";

vi.mock("./AuthContext", () => ({
  useAuth: vi.fn(),
}));
vi.mock("./usePasswordGate", () => ({
  usePasswordGate: vi.fn(),
}));

import { useAuth } from "./AuthContext";
import { usePasswordGate } from "./usePasswordGate";

function authState(role: string, hasUser = true) {
  return {
    user: hasUser ? ({ uid: "u1", email: "u@test.com" } as unknown as import("firebase/auth").User) : null,
    claims: { role },
    loading: false,
    idToken: "tok",
    signIn: vi.fn(),
    signInWithGoogle: vi.fn(),
    signOut: vi.fn(),
  };
}

describe("TenantAdminRoute", () => {
  it("redirects platform_admin to / (not rendered)", () => {
    vi.mocked(useAuth).mockReturnValue(authState("platform_admin"));
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: false, loading: false });
    render(
      <MemoryRouter>
        <TenantAdminRoute><div>Tenant Panel</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Tenant Panel")).not.toBeInTheDocument();
  });

  it("redirects resident to / (not rendered)", () => {
    vi.mocked(useAuth).mockReturnValue(authState("resident"));
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: false, loading: false });
    render(
      <MemoryRouter>
        <TenantAdminRoute><div>Tenant Panel</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Tenant Panel")).not.toBeInTheDocument();
  });

  it("renders children for tenant_admin when flag is false", () => {
    vi.mocked(useAuth).mockReturnValue(authState("tenant_admin"));
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: false, loading: false });
    render(
      <MemoryRouter>
        <TenantAdminRoute><div>Tenant Dashboard</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.getByText("Tenant Dashboard")).toBeInTheDocument();
  });

  it("redirects to /signin when not logged in", () => {
    vi.mocked(useAuth).mockReturnValue({ ...authState("tenant_admin", false), user: null });
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: false, loading: false });
    render(
      <MemoryRouter>
        <TenantAdminRoute><div>Tenant Dashboard</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Tenant Dashboard")).not.toBeInTheDocument();
  });

  it("redirects to /force-password when must_change_password is true", () => {
    vi.mocked(useAuth).mockReturnValue(authState("tenant_admin"));
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: true, loading: false });
    render(
      <MemoryRouter initialEntries={["/tenant"]}>
        <TenantAdminRoute><div>Tenant Dashboard</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Tenant Dashboard")).not.toBeInTheDocument();
  });

  it("renders children when must_change_password is false", () => {
    vi.mocked(useAuth).mockReturnValue(authState("tenant_admin"));
    vi.mocked(usePasswordGate).mockReturnValue({ mustChange: false, loading: false });
    render(
      <MemoryRouter>
        <TenantAdminRoute><div>Protected Content</div></TenantAdminRoute>
      </MemoryRouter>,
    );
    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });
});
