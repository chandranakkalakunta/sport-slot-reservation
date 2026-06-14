import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

import {
  useCreateFacility, useDeactivateFacility, useFacilityCatalog,
  useTenantFacilities,
} from "../../hooks/tenantAdminHooks";
import TenantFacilities from "./TenantFacilities";

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useFacilityCatalog: vi.fn(),
  useTenantFacilities: vi.fn(),
  useCreateFacility: vi.fn(),
  useDeactivateFacility: vi.fn(),
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

const CATALOG_ITEMS = [
  { type_id: "badminton", name: "Badminton", sport: "badminton" },
];
const ACTIVE_FACILITY = {
  id: "fac-1", facility_type_id: "badminton", sport: "badminton",
  name: "North Court", open_time: "06:00", close_time: "22:00",
  slot_duration_minutes: 60, active: true, description: null,
};

beforeEach(() => {
  vi.mocked(useFacilityCatalog).mockReturnValue({
    data: { items: CATALOG_ITEMS },
  } as unknown as ReturnType<typeof useFacilityCatalog>);
  vi.mocked(useTenantFacilities).mockReturnValue({
    data: { items: [ACTIVE_FACILITY] },
    isLoading: false,
  } as unknown as ReturnType<typeof useTenantFacilities>);
  vi.mocked(useCreateFacility).mockImplementation(
    () => ({ mutateAsync: vi.fn().mockResolvedValue(ACTIVE_FACILITY), isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
  );
  vi.mocked(useDeactivateFacility).mockImplementation(
    () => ({ mutate: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useDeactivateFacility>,
  );
});

function renderPage() {
  return render(
    <MemoryRouter>
      <TenantFacilities />
    </MemoryRouter>,
  );
}

describe("TenantFacilities", () => {
  it("lists active facilities", () => {
    renderPage();
    expect(screen.getByText("North Court")).toBeInTheDocument();
    expect(screen.getByText(/badminton/)).toBeInTheDocument();
  });

  it("fires create mutation on valid form submit", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useCreateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    // Select the catalog type
    await user.selectOptions(screen.getByRole("combobox"), "badminton");
    // Fill name (first textbox after the select)
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "South Court");

    await user.click(screen.getByRole("button", { name: /add facility/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ facility_type_id: "badminton", name: "South Court" }),
      );
    });
  });

  it("fires deactivate mutation when Remove clicked", async () => {
    const mutate = vi.fn();
    vi.mocked(useDeactivateFacility).mockImplementation(
      () => ({ mutate, isPending: false }) as unknown as ReturnType<typeof useDeactivateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(mutate).toHaveBeenCalledWith("fac-1");
  });
});
