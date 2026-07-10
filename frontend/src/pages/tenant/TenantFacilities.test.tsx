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
  { type_id: "table-tennis", name: "Table Tennis", sport: "table-tennis" },
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

const FACILITY_B = {
  id: "fac-2", facility_type_id: "table-tennis", sport: "table-tennis",
  name: "South Table",
  weekly_schedule: {
    monday: [{ start: "09:00", end: "17:00" }],
    tuesday: [{ start: "09:00", end: "17:00" }],
    wednesday: [], thursday: [], friday: [], saturday: [], sunday: [],
  },
  slot_duration_minutes: 30, active: true, description: null,
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
  // ── Existing tests (preserved, unweakened) ──────────────────────────────────

  it("lists active facilities using catalog display name, not raw sport slug", () => {
    renderPage();
    expect(screen.getByText("North Court")).toBeInTheDocument();
    // "Badminton" appears in the list item AND the <option>; use getAllByText.
    expect(screen.getAllByText(/Badminton/).length).toBeGreaterThan(0);
  });

  // ── New: price_paise (Phase 15.1) ───────────────────────────────────────────

  it("facility list shows 'No price set' for a facility with no price_paise, not ₹0.00", () => {
    renderPage();
    expect(screen.getByText(/No price set/i)).toBeInTheDocument();
    expect(screen.queryByText(/₹0\.00/)).not.toBeInTheDocument();
  });

  it("facility list shows the formatted rupee price when price_paise is set", () => {
    vi.mocked(useTenantFacilities).mockReturnValue({
      data: { items: [{ ...ACTIVE_FACILITY, price_paise: 5050 }] },
      isLoading: false,
    } as unknown as ReturnType<typeof useTenantFacilities>);
    renderPage();
    expect(screen.getByText(/₹50\.50/)).toBeInTheDocument();
  });

  it("create form converts entered rupees to integer paise (50.50 -> 5050) on submit", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useCreateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "badminton");
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "South Court");
    await user.type(screen.getByLabelText(/price per booking/i), "50.50");

    await user.click(screen.getByRole("button", { name: /add facility/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ price_paise: 5050 }),
      );
    });
  });

  it("create form omits price_paise (undefined) when the price field is left empty", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useCreateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "badminton");
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "South Court");

    await user.click(screen.getByRole("button", { name: /add facility/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ price_paise: undefined }),
      );
    });
  });

  it("edit dialog pre-populates price in rupees from the facility's price_paise", async () => {
    vi.mocked(useTenantFacilities).mockReturnValue({
      data: { items: [{ ...ACTIVE_FACILITY, price_paise: 5050 }] },
      isLoading: false,
    } as unknown as ReturnType<typeof useTenantFacilities>);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    const dialog = screen.getByRole("dialog", { name: /edit facility/i });
    expect(within(dialog).getByLabelText(/price per booking/i)).toHaveValue(50.5);
  });

  it("edit dialog shows an empty price field for a facility with no price_paise", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    const dialog = screen.getByRole("dialog", { name: /edit facility/i });
    expect(within(dialog).getByLabelText(/price per booking/i)).toHaveValue(null);
  });

  it("create form initializes with the default schedule (06-10 + 16-21 on all 7 days)", async () => {
    renderPage();
    // The weekly editor shows all 7 days; each day should show the default ranges summary
    const summaries = screen.getAllByText("06:00–10:00, 16:00–21:00");
    expect(summaries.length).toBe(7);
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
            monday: [{ start: "06:00", end: "10:00" }, { start: "16:00", end: "21:00" }],
            sunday: [{ start: "06:00", end: "10:00" }, { start: "16:00", end: "21:00" }],
          }),
        }),
      );
    });
  });

  it("edit dialog opens pre-filled with the facility's real schedule, not the default", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    const dialog = screen.getByRole("dialog", { name: /edit facility/i });
    // Facility's real monday schedule: 06:00-22:00 (not the default 06:00-10:00, 16:00-21:00).
    // Mon-Fri all have this range, so multiple rows match — use getAllByText.
    expect(within(dialog).getAllByText("06:00–22:00").length).toBeGreaterThan(0);
    expect(within(dialog).queryByText("06:00–10:00, 16:00–21:00")).not.toBeInTheDocument();
  });

  it("edit dialog opens pre-filled and fires update mutation with correct payload", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useUpdateFacility).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useUpdateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    const dialog = screen.getByRole("dialog", { name: /edit facility/i });
    expect(within(dialog).getByDisplayValue("North Court")).toBeInTheDocument();

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

  it("edit dialog shows facility B's schedule after switching from facility A (stale-state regression)", async () => {
    // Two facilities: A (06:00-22:00 mon) and B (09:00-17:00 mon)
    vi.mocked(useTenantFacilities).mockReturnValue({
      data: { items: [ACTIVE_FACILITY, FACILITY_B] },
      isLoading: false,
    } as unknown as ReturnType<typeof useTenantFacilities>);

    const user = userEvent.setup();
    renderPage();

    // Open edit for North Court (A)
    const editButtons = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editButtons[0]); // North Court (sorted alphabetically first)

    let dialog = screen.getByRole("dialog", { name: /edit facility/i });
    expect(within(dialog).getByDisplayValue("North Court")).toBeInTheDocument();

    // Close the dialog
    const closeBtn = within(dialog).getByRole("button", { name: /close/i });
    await user.click(closeBtn);

    // Open edit for South Table (B)
    const editButtons2 = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editButtons2[1]); // South Table (second after sort)

    dialog = screen.getByRole("dialog", { name: /edit facility/i });
    // Must show B's name and B's monday schedule (09:00-17:00), not A's (06:00-22:00).
    // Mon+Tue both have "09:00-17:00", so multiple rows match — use getAllByText.
    expect(within(dialog).getByDisplayValue("South Table")).toBeInTheDocument();
    expect(within(dialog).getAllByText("09:00–17:00").length).toBeGreaterThan(0);
    expect(within(dialog).queryByText("06:00–22:00")).not.toBeInTheDocument();
  });

  it("fires deactivate mutation after confirming Remove in dialog", async () => {
    const mutate = vi.fn();
    vi.mocked(useDeactivateFacility).mockImplementation(
      () => ({ mutate, isPending: false }) as unknown as ReturnType<typeof useDeactivateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /remove/i }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    expect(mutate).toHaveBeenCalledWith("fac-1");
  });

  // ── New: Clone tests ────────────────────────────────────────────────────────

  it("clone opens dialog with type/duration/schedule pre-filled and name/description empty", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^clone$/i }));

    const dialog = screen.getByRole("dialog", { name: /clone facility/i });
    // Name must be empty — not "North Court"
    expect(within(dialog).getByLabelText(/^name$/i)).toHaveValue("");
    // Description must be empty
    expect(within(dialog).getByLabelText(/description/i)).toHaveValue("");
    // Duration pre-filled from source (60)
    expect(within(dialog).getByLabelText(/slot duration/i)).toHaveValue(60);
    // Schedule pre-filled — Mon-Fri all show 06:00-22:00 from source facility
    expect(within(dialog).getAllByText("06:00–22:00").length).toBeGreaterThan(0);
  });

  it("clone save fires createFacility.mutateAsync, not updateFacility.mutateAsync", async () => {
    const createMutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    const updateMutateAsync = vi.fn().mockResolvedValue(ACTIVE_FACILITY);
    vi.mocked(useCreateFacility).mockImplementation(
      () => ({ mutateAsync: createMutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateFacility>,
    );
    vi.mocked(useUpdateFacility).mockImplementation(
      () => ({ mutateAsync: updateMutateAsync, isPending: false }) as unknown as ReturnType<typeof useUpdateFacility>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^clone$/i }));

    const dialog = screen.getByRole("dialog", { name: /clone facility/i });
    // Provide a name (required field) before saving
    await user.type(within(dialog).getByLabelText(/^name$/i), "North Court Copy");

    await user.click(within(dialog).getByRole("button", { name: /create clone/i }));

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          facility_type_id: "badminton",
          name: "North Court Copy",
          slot_duration_minutes: 60,
          weekly_schedule: expect.objectContaining({
            monday: [{ start: "06:00", end: "22:00" }],
          }),
        }),
      );
      // Must NOT have been called with an id field
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.not.objectContaining({ id: expect.anything() }),
      );
    });
    // updateFacility must never fire
    expect(updateMutateAsync).not.toHaveBeenCalled();
  });

  it("opening Edit(A) then Clone(A) shows blanked name/description, not stale edit-name", async () => {
    const user = userEvent.setup();
    renderPage();

    // Open Edit for North Court (A) — fills editName = "North Court"
    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    let dialog = screen.getByRole("dialog", { name: /edit facility/i });
    expect(within(dialog).getByDisplayValue("North Court")).toBeInTheDocument();

    // Close
    await user.click(within(dialog).getByRole("button", { name: /close/i }));

    // Open Clone for North Court (A) — must show blank name, not "North Court"
    await user.click(screen.getByRole("button", { name: /^clone$/i }));
    dialog = screen.getByRole("dialog", { name: /clone facility/i });
    expect(within(dialog).getByLabelText(/^name$/i)).toHaveValue("");
    expect(within(dialog).queryByDisplayValue("North Court")).not.toBeInTheDocument();
  });

  it("dialog title shows 'Edit facility' in edit mode and 'Clone facility' in clone mode", async () => {
    const user = userEvent.setup();
    renderPage();

    // Edit mode
    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(screen.getByRole("dialog", { name: "Edit facility" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: /close/i }));

    // Clone mode
    await user.click(screen.getByRole("button", { name: /^clone$/i }));
    expect(screen.getByRole("dialog", { name: "Clone facility" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: /close/i }));
  });
});
