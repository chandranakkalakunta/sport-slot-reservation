import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

import {
  useCreateFacility, useDeactivateFacility, useFacilityCatalog,
  useTenantFacilities, useUpdateFacility,
} from "../../hooks/tenantAdminHooks";
import TenantFacilities from "./TenantFacilities";

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useFacilityCatalog: vi.fn(),
  useTenantFacilities: vi.fn(),
  useCreateFacility: vi.fn(),
  useDeactivateFacility: vi.fn(),
  useUpdateFacility: vi.fn(),
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
  name: "North Court",
  weekly_schedule: {
    monday: [{ start: "06:00", end: "22:00" }],
    tuesday: [{ start: "06:00", end: "22:00" }],
    wednesday: [{ start: "06:00", end: "22:00" }],
    thursday: [{ start: "06:00", end: "22:00" }],
    friday: [{ start: "06:00", end: "22:00" }],
    saturday: [],
    sunday: [],
  },
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
  vi.mocked(useUpdateFacility).mockImplementation(
    () => ({ mutateAsync: vi.fn().mockResolvedValue(ACTIVE_FACILITY), isPending: false }) as unknown as ReturnType<typeof useUpdateFacility>,
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

  it("fires create mutation with weekly_schedule on valid form submit", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useCreateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    // Select the catalog type (use the create form's combobox — first one on page)
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "badminton");
    // Fill name — first textbox is facility-name
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "South Court");

    await user.click(screen.getByRole("button", { name: /add facility/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          facility_type_id: "badminton",
          name: "South Court",
          weekly_schedule: expect.objectContaining({
            monday: expect.any(Array),
            tuesday: expect.any(Array),
            wednesday: expect.any(Array),
            thursday: expect.any(Array),
            friday: expect.any(Array),
            saturday: expect.any(Array),
            sunday: expect.any(Array),
          }),
        }),
      );
    });
  });

  it("edit dialog opens pre-filled and fires update mutation with correct payload", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useUpdateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useUpdateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    // Open edit dialog for North Court
    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    const dialog = screen.getByRole("dialog", { name: /edit facility/i });
    // Pre-filled name
    expect(within(dialog).getByDisplayValue("North Court")).toBeInTheDocument();

    // Change the name
    const nameInput = within(dialog).getByDisplayValue("North Court");
    await user.clear(nameInput);
    await user.type(nameInput, "South Court");

    await user.click(within(dialog).getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "fac-1",
          name: "South Court",
          weekly_schedule: expect.objectContaining({
            monday: expect.any(Array),
          }),
        }),
      );
    });
  });

  it("fires deactivate mutation after confirming Remove in dialog", async () => {
    const mutate = vi.fn();
    vi.mocked(useDeactivateFacility).mockImplementation(
      () => ({ mutate, isPending: false }) as unknown as ReturnType<typeof useDeactivateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    // De-emphasized trigger opens the ConfirmDialog (ADR-0028 §5 destructive posture)
    await user.click(screen.getByRole("button", { name: /remove/i }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    expect(mutate).toHaveBeenCalledWith("fac-1");
  });
});
