import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../components/AppHeader", () => ({ AppHeader: () => null }));

// No importOriginal — avoids loading real bookingHooks → api.ts → firebase.ts
// (which throws auth/invalid-api-key in CI where no Firebase env vars exist).
vi.mock("../hooks/bookingHooks", () => ({
  useFacilities: vi.fn(),
}));

import * as hooks from "../hooks/bookingHooks";
import Facilities from "./Facilities";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const FACILITY = {
  id: "f1",
  name: "Tennis Court A",
  sport: "tennis",
  weekly_schedule: {
    monday: [{ start: "07:00", end: "21:00" }],
    tuesday: [{ start: "07:00", end: "21:00" }],
    wednesday: [{ start: "07:00", end: "21:00" }],
    thursday: [{ start: "07:00", end: "21:00" }],
    friday: [{ start: "07:00", end: "21:00" }],
    saturday: [],
    sunday: [],
  },
  slot_duration_minutes: 60,
  active: true,
};

afterEach(() => {
  vi.useRealTimers();
});

describe("Facilities", () => {
  it("renders the page heading", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByRole("heading", { name: "Facilities" })).toBeInTheDocument();
  });

  it("renders a facility from mock data", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [FACILITY], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText("Tennis Court A")).toBeInTheDocument();
  });

  it("links each facility to its availability page", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [FACILITY], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByRole("link", { name: /Tennis Court A/i })).toHaveAttribute(
      "href",
      "/facilities/f1",
    );
  });

  it("shows loading state", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText("Loading facilities…")).toBeInTheDocument();
  });

  it("shows error state", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("network"),
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText("Couldn't load facilities.")).toBeInTheDocument();
  });

  it("filters out inactive facilities", () => {
    const inactive = { ...FACILITY, id: "f2", name: "Closed Court", active: false };
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [FACILITY, inactive], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText("Tennis Court A")).toBeInTheDocument();
    expect(screen.queryByText("Closed Court")).not.toBeInTheDocument();
  });

  it("shows empty state when no active facilities", () => {
    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText("No facilities available.")).toBeInTheDocument();
  });

  it("shows today's hours when the facility is open today", () => {
    // Pin to a Monday (2024-01-01 is a Monday)
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-01T10:00:00"));

    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [FACILITY], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText(/Today: 07:00–21:00/)).toBeInTheDocument();
  });

  it("shows 'Closed today' when the facility has no ranges for today", () => {
    // Pin to a Saturday (2024-01-06 is a Saturday)
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-06T10:00:00"));

    vi.spyOn(hooks, "useFacilities").mockReturnValue({
      data: { items: [FACILITY], next_cursor: null },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useFacilities>);

    wrap(<Facilities />);
    expect(screen.getByText(/Closed today/)).toBeInTheDocument();
  });
});
