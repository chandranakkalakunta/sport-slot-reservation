import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiFetch: vi.fn(),
  ApiClientError: class ApiClientError extends Error {},
}));
vi.mock("../auth/AuthContext", () => ({ useAuth: vi.fn() }));

import { useAuth } from "../auth/AuthContext";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { PASSWORD_GATE_QUERY_KEY } from "../auth/usePasswordGate";
import { apiFetch } from "../lib/api";
import ForcePasswordChange from "./ForcePasswordChange";

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    user: { uid: "u1" } as unknown as import("firebase/auth").User,
    idToken: "tok",
    claims: { role: "resident" },
    loading: false,
    signIn: vi.fn(),
    signInWithGoogle: vi.fn(),
    signOut: vi.fn(),
  });
});

async function submitNewPassword() {
  fireEvent.change(screen.getByPlaceholderText("New password"), {
    target: { value: "newpassword123" },
  });
  fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
    target: { value: "newpassword123" },
  });
  fireEvent.click(screen.getByRole("button", { name: /set password/i }));
}

test("a freshly-mounted gate observer reads must_change_password=false on its FIRST render after a successful change", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Seed exactly like reality: the gate fetched once elsewhere (true),
  // then its observer unmounted — /force-password itself never mounts
  // usePasswordGate, so there is zero active observer for this key
  // while the change-password flow below runs.
  qc.setQueryData(PASSWORD_GATE_QUERY_KEY, { must_change_password: true });

  vi.mocked(apiFetch).mockImplementation(async (path: string) => {
    if (path === "/users/me/change-password") return {};
    if (path === "/users/me") return { must_change_password: false };
    throw new Error(`unexpected path: ${path}`);
  });

  const { unmount } = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/force-password"]}>
        <ForcePasswordChange />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await submitNewPassword();

  // Wait only for the form's own busy-state signal — never for
  // navigation or the gate. This keeps zero active gate observers
  // mounted while the refresh logic runs, exactly like the real
  // standalone /force-password route.
  await waitFor(() => expect(screen.queryByText("Saving…")).not.toBeInTheDocument());

  unmount(); // No gate observer was ever mounted up to this point.

  // Mount a BRAND NEW observer — exactly what ProtectedRoute does the
  // instant navigate("/") lands. The assertion below reads the very
  // first render with no waitFor: if the cache still held the stale
  // `true`, ProtectedRoute would render <Navigate> instead of
  // children on this first render, and "Home" would be absent.
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <ProtectedRoute>
          <div>Home</div>
        </ProtectedRoute>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.getByText("Home")).toBeInTheDocument();
});
