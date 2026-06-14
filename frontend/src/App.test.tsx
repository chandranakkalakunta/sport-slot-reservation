import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("./lib/branding", () => ({ loadBrandingForSlug: vi.fn() }));
vi.mock("./lib/api", () => ({ apiFetch: vi.fn() }));

// Mock Firebase Auth at the module boundary (no real auth in unit tests).
let idTokenCallback: ((u: unknown) => void) | null = null;
vi.mock("./lib/firebase", () => ({
  auth: { currentUser: null },
  firebaseApp: {},
}));
vi.mock("firebase/auth", () => ({
  onIdTokenChanged: (_auth: unknown, cb: (u: unknown) => void) => {
    idTokenCallback = cb;
    return () => {};
  },
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: class {},
}));

import { apiFetch } from "./lib/api";
import App from "./App";

beforeEach(() => {
  idTokenCallback = null;
});

test("unauthenticated user is redirected to sign-in", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  // Resolve auth state as logged-out.
  idTokenCallback?.(null);
  await waitFor(() =>
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument(),
  );
});

test("loading state shows before auth resolves", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByText("Loading…")).toBeInTheDocument();
});

test("tenant_admin with must_change_password=true is redirected to /force-password", async () => {
  vi.mocked(apiFetch).mockResolvedValue({ must_change_password: true });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  idTokenCallback?.({
    email: "admin@example.com",
    getIdTokenResult: async () => ({
      token: "tok",
      claims: { role: "tenant_admin", tenant_slug: "demo" },
    }),
  });

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: /set a new password/i })).toBeInTheDocument();
  });
});
