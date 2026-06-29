import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";

// Mock Firebase BEFORE importing App (which imports AuthContext → lib/firebase).
// In jsdom, Firebase initializes with undefined env vars and onIdTokenChanged
// may never call its callback, leaving AuthProvider loading=true forever.
// This mock fires immediately with null user (unauthenticated), which is the
// production-equivalent fast path for an unauthenticated visitor.
vi.mock("./lib/firebase", () => ({ firebaseApp: {}, auth: {} }));
vi.mock("firebase/auth", () => ({
  onIdTokenChanged: (_auth: unknown, cb: (u: null) => void) => {
    cb(null);
    return () => {};
  },
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  GoogleAuthProvider: vi.fn(),
  signOut: vi.fn(),
}));

import App from "./App";

describe("app render — production-equivalent mount guard", () => {
  it("renders SignIn at route / when unauthenticated (blank-page regression guard)", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // ProtectedRoute sees loading=false + no user → Navigate to /signin → SignIn renders.
    // SignIn.tsx renders <h1>SlotSense</h1> and <button type="submit">Sign in</button>.
    // A timeout here means blank page — the guard catches it.
    expect(
      await screen.findByRole("heading", { name: "SlotSense" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
  });
});
