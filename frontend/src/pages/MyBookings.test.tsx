import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../components/AppHeader", () => ({
  AppHeader: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../hooks/bookingHooks", () => ({
  useMyBookings: vi.fn(),
  useFacilities: vi.fn(),
  useCancelBooking: vi.fn(),
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
import { ApiClientError } from "../lib/api";
import MyBookings from "./MyBookings";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const BOOKING = {
  id: "b1", facility_id: "f1", date: "2027-01-15",
  start: "09:00", end: "10:00", status: "confirmed", cancellable: true,
};

const FAC_STUB = {
  data: { items: [] }, isLoading: false,
} as unknown as ReturnType<typeof hooks.useFacilities>;

const CANCEL_STUB = {
  mutateAsync: vi.fn(), isPending: false,
} as unknown as ReturnType<typeof hooks.useCancelBooking>;

it("renders confirmed booking", () => {
  vi.mocked(hooks.useMyBookings).mockReturnValue({
    data: { items: [BOOKING] }, isLoading: false,
  } as ReturnType<typeof hooks.useMyBookings>);
  vi.mocked(hooks.useFacilities).mockReturnValue({
    data: { items: [{ id: "f1", name: "Tennis Court", sport: "tennis",
      weekly_schedule: {
        monday: [{ start: "07:00", end: "21:00" }],
        tuesday: [{ start: "07:00", end: "21:00" }],
        wednesday: [{ start: "07:00", end: "21:00" }],
        thursday: [{ start: "07:00", end: "21:00" }],
        friday: [{ start: "07:00", end: "21:00" }],
        saturday: [], sunday: [],
      },
      slot_duration_minutes: 60, active: true }] },
    isLoading: false,
  } as unknown as ReturnType<typeof hooks.useFacilities>);
  vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

  wrap(<MyBookings />);

  expect(screen.getByText("Tennis Court")).toBeInTheDocument();
  expect(screen.getByText(/2027-01-15/)).toBeInTheDocument();
});

it("renders all items from backend without client-side date filtering", () => {
  // Backend is now the authoritative filter.  The frontend renders whatever
  // the endpoint returns — no UTC date cutoff drops items client-side.
  const todayBooking = { ...BOOKING, id: "b-today", date: "2026-06-30" };
  const futureBooking = { ...BOOKING, id: "b-future", date: "2027-01-15" };

  vi.mocked(hooks.useMyBookings).mockReturnValue({
    data: { items: [todayBooking, futureBooking] }, isLoading: false,
  } as ReturnType<typeof hooks.useMyBookings>);
  vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
  vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

  wrap(<MyBookings />);

  // Both dates from the backend response must appear (no client-side cutoff).
  expect(screen.getByText(/2026-06-30/)).toBeInTheDocument();
  expect(screen.getByText(/2027-01-15/)).toBeInTheDocument();
});

it("renders the shared resident nav (Facilities + My bookings) in the header, replacing the old manual back-link", () => {
  vi.mocked(hooks.useMyBookings).mockReturnValue({
    data: { items: [] }, isLoading: false,
  } as unknown as ReturnType<typeof hooks.useMyBookings>);
  vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
  vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

  wrap(<MyBookings />);

  expect(screen.getByRole("link", { name: "Facilities" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("link", { name: "My bookings" })).toHaveAttribute("href", "/bookings");
  // The old page-body "← Facilities" text link is gone now that the header covers it.
  expect(screen.queryByText("← Facilities")).not.toBeInTheDocument();
});

it("shows No upcoming bookings when backend returns empty list", () => {
  vi.mocked(hooks.useMyBookings).mockReturnValue({
    data: { items: [] }, isLoading: false,
  } as unknown as ReturnType<typeof hooks.useMyBookings>);
  vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
  vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

  wrap(<MyBookings />);

  expect(screen.getByText("No upcoming bookings.")).toBeInTheDocument();
});

it("shows Cancellation closed when cancellable is false", () => {
  const nonCancellable = { ...BOOKING, cancellable: false };
  vi.mocked(hooks.useMyBookings).mockReturnValue({
    data: { items: [nonCancellable] }, isLoading: false,
  } as ReturnType<typeof hooks.useMyBookings>);
  vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
  vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

  wrap(<MyBookings />);

  expect(screen.getByText("Cancellation closed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
});

describe("cancellation dialog", () => {
  it("opens confirm dialog when Cancel clicked", async () => {
    vi.mocked(hooks.useMyBookings).mockReturnValue({
      data: { items: [BOOKING] }, isLoading: false,
    } as ReturnType<typeof hooks.useMyBookings>);
    vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
    vi.mocked(hooks.useCancelBooking).mockReturnValue(CANCEL_STUB);

    wrap(<MyBookings />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/cancel your 09:00 booking/i)).toBeInTheDocument();
  });

  it("shows error in dialog on cancellation failure and keeps dialog open", async () => {
    vi.mocked(hooks.useMyBookings).mockReturnValue({
      data: { items: [BOOKING] }, isLoading: false,
    } as ReturnType<typeof hooks.useMyBookings>);
    vi.mocked(hooks.useFacilities).mockReturnValue(FAC_STUB);
    vi.mocked(hooks.useCancelBooking).mockReturnValue({
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
