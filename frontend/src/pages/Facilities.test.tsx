import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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
  open_time: "07:00",
  close_time: "21:00",
  slot_duration_minutes: 60,
  active: true,
};

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
});
