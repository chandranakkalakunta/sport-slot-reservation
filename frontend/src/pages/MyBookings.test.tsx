import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../components/AppHeader", () => ({ AppHeader: () => null }));

import * as hooks from "../hooks/bookingHooks";
import { ApiClientError } from "../lib/api";
import MyBookings from "./MyBookings";

vi.mock("../hooks/bookingHooks", async (importOriginal) => {
  const real = await importOriginal<typeof hooks>();
  return { ...real };
});

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

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const BOOKING = {
  id: "b1", facility_id: "f1", date: "2026-06-15",
  start: "09:00", end: "10:00", status: "confirmed", cancellable: true,
};

it("renders confirmed booking", () => {
  vi.spyOn(hooks, "useMyBookings").mockReturnValue({
    data: { items: [BOOKING] }, isLoading: false,
  } as ReturnType<typeof hooks.useMyBookings>);
  vi.spyOn(hooks, "useFacilities").mockReturnValue({
    data: { items: [{ id: "f1", name: "Tennis Court", sport: "tennis",
      open_time: "07:00", close_time: "21:00", slot_duration_minutes: 60,
      active: true }] },
    isLoading: false,
  } as ReturnType<typeof hooks.useFacilities>);
  vi.spyOn(hooks, "useCancelBooking").mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof hooks.useCancelBooking>);

  wrap(<MyBookings />);

  expect(screen.getByText("Tennis Court")).toBeInTheDocument();
  expect(screen.getByText(/2026-06-15/)).toBeInTheDocument();
});

it("shows Cancellation closed when cancellable is false", () => {
  const nonCancellable = { ...BOOKING, cancellable: false };
  vi.spyOn(hooks, "useMyBookings").mockReturnValue({
    data: { items: [nonCancellable] }, isLoading: false,
  } as ReturnType<typeof hooks.useMyBookings>);
  vi.spyOn(hooks, "useFacilities").mockReturnValue({
    data: { items: [] }, isLoading: false,
  } as unknown as ReturnType<typeof hooks.useFacilities>);
  vi.spyOn(hooks, "useCancelBooking").mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof hooks.useCancelBooking>);

  wrap(<MyBookings />);

  expect(screen.getByText("Cancellation closed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
});

describe("cancellation dialog", () => {
  it("opens confirm dialog when Cancel clicked", async () => {
    vi.spyOn(hooks, "useMyBookings").mockReturnValue({
      data: { items: [BOOKING] }, isLoading: false,
    } as ReturnType<typeof hooks.useMyBookings>);
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useFacilities>);
    vi.spyOn(hooks, "useCancelBooking").mockReturnValue({
      mutateAsync: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof hooks.useCancelBooking>);

    wrap(<MyBookings />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/cancel your 09:00 booking/i)).toBeInTheDocument();
  });

  it("shows error in dialog on cancellation failure and keeps dialog open", async () => {
    vi.spyOn(hooks, "useMyBookings").mockReturnValue({
      data: { items: [BOOKING] }, isLoading: false,
    } as ReturnType<typeof hooks.useMyBookings>);
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof hooks.useFacilities>);
    vi.spyOn(hooks, "useCancelBooking").mockReturnValue({
      mutateAsync: vi.fn().mockRejectedValue(
        new ApiClientError({ code: "CANCELLATION_TOO_LATE", message: "too late", status: 422 }),
      ),
      isPending: false,
    } as unknown as ReturnType<typeof hooks.useCancelBooking>);

    wrap(<MyBookings />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel booking" }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText(/too late to cancel/i)).toBeInTheDocument();
    });
  });
});
