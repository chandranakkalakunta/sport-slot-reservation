import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

// No importOriginal — avoids loading real tenantAdminHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../../hooks/tenantAdminHooks", () => ({
  useUpdatePolicies: vi.fn(),
  usePolicies: vi.fn(),
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

import { usePolicies, useUpdatePolicies } from "../../hooks/tenantAdminHooks";
import TenantPolicies from "./TenantPolicies";

function renderPage() {
  return render(<MemoryRouter><TenantPolicies /></MemoryRouter>);
}

describe("TenantPolicies", () => {
  beforeEach(() => {
    vi.mocked(useUpdatePolicies).mockImplementation(
      () => ({ mutateAsync: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useUpdatePolicies>,
    );
    // No data loaded (policy not yet fetched) — form shows hardcoded defaults.
    vi.mocked(usePolicies).mockReturnValue({
      data: undefined, isLoading: false,
    } as unknown as ReturnType<typeof usePolicies>);
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

  // ── Regression: fetch-on-mount populates form from real data (the bug this fixes) ──
  //
  // The form used to show hardcoded defaults (horizon=14, buffer=1, max=2) regardless
  // of what the server had saved. This test mocks the GET with the exact Firestore
  // values confirmed in the bug report and asserts the rendered inputs show those
  // real values — not the old literals.
  it("populates form with fetched values, not hardcoded defaults (regression)", async () => {
    vi.mocked(usePolicies).mockReturnValue({
      data: {
        policies: {
          booking_horizon_days: 2,
          booking_window_open_time: "08:00",
          cancellation_buffer_hours: 1,
          max_slots_per_user_per_sport_per_day: 1,
        },
      },
      isLoading: false,
    } as unknown as ReturnType<typeof usePolicies>);

    renderPage();

    // booking_horizon_days: fetched=2, hardcoded-default=14 — must show 2, not 14
    await waitFor(() => {
      expect(screen.getByLabelText(/booking horizon/i)).toHaveValue(2);
    });
    // max_slots: fetched=1, hardcoded-default=2 — must show 1, not 2
    expect(screen.getByLabelText(/max slots/i)).toHaveValue(1);
    // booking_window_open_time: fetched="08:00", hardcoded-default="06:00"
    expect(screen.getByLabelText(/booking window opens at/i)).toHaveValue("08:00");
    // cancellation_buffer_hours: fetched=1, hardcoded-default=1 — same; verify it renders
    expect(screen.getByLabelText(/cancellation buffer/i)).toHaveValue(1);
  });

  it("keeps hardcoded defaults when no policies are saved yet (empty server response)", () => {
    vi.mocked(usePolicies).mockReturnValue({
      data: { policies: {} },
      isLoading: false,
    } as unknown as ReturnType<typeof usePolicies>);

    renderPage();

    // All fields absent from server → keep defaults
    expect(screen.getByLabelText(/booking horizon/i)).toHaveValue(14);
    expect(screen.getByLabelText(/max slots/i)).toHaveValue(2);
  });
});
