import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// No importOriginal — avoids loading real bookingHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../hooks/bookingHooks", () => ({
  useAvailability: vi.fn(),
  useCreateBooking: vi.fn(),
  useMyBookings: vi.fn(),
}));

vi.mock("../lib/api", () => ({
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

import * as hooks from "../hooks/bookingHooks";
import FacilityAvailability from "./FacilityAvailability";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/facilities/f1"]}>
        <Routes>
          <Route path="/facilities/:facilityId" element={<FacilityAvailability />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FacilityAvailability", () => {
  beforeEach(() => {
    vi.spyOn(hooks, "useAvailability").mockReturnValue({
      data: undefined, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useAvailability>);
    vi.spyOn(hooks, "useCreateBooking").mockReturnValue({
      mutateAsync: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof hooks.useCreateBooking>);
    vi.spyOn(hooks, "useMyBookings").mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyBookings>);
  });

  it("renders the Availability heading", () => {
    wrap();
    expect(screen.getByRole("heading", { name: "Availability" })).toBeInTheDocument();
  });

  it("renders the date input", () => {
    wrap();
    expect(screen.getByLabelText("Date")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    vi.spyOn(hooks, "useAvailability").mockReturnValue({
      data: undefined, isLoading: true,
    } as unknown as ReturnType<typeof hooks.useAvailability>);
    wrap();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders available slot from API", () => {
    vi.spyOn(hooks, "useAvailability").mockReturnValue({
      data: {
        facility_id: "f1",
        date: "2027-01-15",
        slots: [{ start: "08:00", end: "09:00", status: "available" as const, bookable: true, reason: null }],
      },
      isLoading: false,
    } as unknown as ReturnType<typeof hooks.useAvailability>);
    wrap();
    expect(screen.getByText("08:00")).toBeInTheDocument();
  });

  it("shows quota advisory when at quota", () => {
    const today = new Date().toISOString().slice(0, 10);
    vi.spyOn(hooks, "useMyBookings").mockReturnValue({
      data: {
        items: [{
          id: "b1", facility_id: "f1", date: today,
          start: "07:00", end: "08:00", status: "confirmed", cancellable: true,
        }],
      },
      isLoading: false,
    } as unknown as ReturnType<typeof hooks.useMyBookings>);
    wrap();
    expect(screen.getByText(/You've used today's booking/)).toBeInTheDocument();
  });
});
