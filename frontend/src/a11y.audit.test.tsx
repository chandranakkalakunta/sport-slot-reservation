/**
 * Phase 10.5 Accessibility Audit
 *
 * Automated axe-core scan across all key pages in light AND dark mode.
 * Also covers: keyboard navigation, ConfirmDialog focus trap, SlotGrid
 * accessible state verification.
 *
 * Infrastructure: jest-axe + vitest/jsdom (no Playwright — Playwright not in
 * project deps; jsdom axe catches structural violations; CSS contrast requires
 * manual/visual check with a running browser — flagged in report below).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe, toHaveNoViolations } from "jest-axe";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

expect.extend(toHaveNoViolations);

// ─── Shared mocks ────────────────────────────────────────────────────────────

vi.mock("./components/AppHeader", () => ({ AppHeader: () => null }));

vi.mock("./auth/AuthContext", () => ({
  useAuth: () => ({ user: null, claims: null, signIn: vi.fn(), signInWithGoogle: vi.fn(), signOut: vi.fn() }),
}));

vi.mock("./hooks/bookingHooks", () => ({
  useFacilities: vi.fn(),
  useFacilityCatalog: vi.fn(),
  useAvailability: vi.fn(),
  useCreateBooking: vi.fn(),
  useMyBookings: vi.fn(),
  useCancelBooking: vi.fn(),
}));

vi.mock("./hooks/tenantAdminHooks", () => ({
  useFacilityCatalog: vi.fn(),
  useTenantFacilities: vi.fn(),
  useCreateFacility: vi.fn(),
  useUpdateFacility: vi.fn(),
  useDeactivateFacility: vi.fn(),
  useTenantUsers: vi.fn(),
  useCreateTenantUser: vi.fn(),
  useDeactivateTenantUser: vi.fn(),
  useResetTenantUserPassword: vi.fn(),
  useBulkCreateUsers: vi.fn(),
  useUpdatePolicies: vi.fn(),
  useUpdateBranding: vi.fn(),
}));

vi.mock("./hooks/adminHooks", () => ({
  useTenants: vi.fn(),
  useCreateTenant: vi.fn(),
  useCreateUser: vi.fn(),
}));

vi.mock("./hooks/agentHooks", () => ({
  useAgentSendMessage: vi.fn(),
  useAgentConfirm: vi.fn(),
  errorMessageFor: vi.fn(),
}));

vi.mock("./lib/api", () => ({
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

vi.mock("./lib/agentSession", () => ({
  loadThread: vi.fn(() => []),
  saveThread: vi.fn(),
  lastUserAndAgentTurn: vi.fn(() => null),
}));

vi.mock("./lib/branding", () => ({
  loadBrandingForSlug: vi.fn(),
  getLastBranding: vi.fn(() => null),
}));

// ─── Imports after mocks ─────────────────────────────────────────────────────

import * as bookingHooks from "./hooks/bookingHooks";
import * as tenantHooks from "./hooks/tenantAdminHooks";
import * as adminHooks from "./hooks/adminHooks";
import * as agentHooks from "./hooks/agentHooks";

import SignIn from "./pages/SignIn";
import Facilities from "./pages/Facilities";
import FacilityAvailability from "./pages/FacilityAvailability";
import MyBookings from "./pages/MyBookings";
import Account from "./pages/Account";
import Assistant from "./pages/Assistant";
import TenantDashboard from "./pages/tenant/TenantDashboard";
import TenantFacilities from "./pages/tenant/TenantFacilities";
import TenantUsers from "./pages/tenant/TenantUsers";
import TenantPolicies from "./pages/tenant/TenantPolicies";
import TenantBranding from "./pages/tenant/TenantBranding";
import TenantList from "./pages/admin/TenantList";
import CreateTenant from "./pages/admin/CreateTenant";
import CreateUser from "./pages/admin/CreateUser";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { SlotGrid } from "./components/SlotGrid";
import { type Slot } from "./hooks/bookingHooks";

// ─── Stub data ────────────────────────────────────────────────────────────────

const EMPTY_SCHEDULE = {
  monday: [], tuesday: [], wednesday: [], thursday: [],
  friday: [], saturday: [], sunday: [],
};
const FACILITY = {
  id: "f1", name: "Tennis Court A", sport: "tennis",
  weekly_schedule: {
    ...EMPTY_SCHEDULE,
    monday: [{ start: "07:00", end: "21:00" }],
    tuesday: [{ start: "07:00", end: "21:00" }],
    wednesday: [{ start: "07:00", end: "21:00" }],
    thursday: [{ start: "07:00", end: "21:00" }],
    friday: [{ start: "07:00", end: "21:00" }],
  },
  slot_duration_minutes: 60, active: true,
};
const SLOTS: Slot[] = [
  { start: "08:00", end: "09:00", status: "available", bookable: true, reason: null },
  { start: "09:00", end: "10:00", status: "booked", bookable: false, reason: "BOOKED" },
  { start: "06:00", end: "07:00", status: "available", bookable: false, reason: "PAST" },
];
const BOOKING = {
  id: "b1", facility_id: "f1", date: "2027-01-15",
  start: "09:00", end: "10:00", status: "confirmed", cancellable: true,
};
const TENANT = {
  tenant_id: "t-1", slug: "oakwood", display_name: "Oakwood", name: "Oakwood", active: true,
};
const TENANT_USER = {
  uid: "u-1", email: "alice@demo.com", display_name: "Alice",
  role: "resident", flat_number: "A-1", active: true,
};
const CATALOG = [{ type_id: "badminton", name: "Badminton", sport: "badminton" }];
const ACTIVE_FAC = {
  id: "fac-1", facility_type_id: "badminton", sport: "badminton",
  name: "North Court",
  weekly_schedule: {
    ...EMPTY_SCHEDULE,
    monday: [{ start: "06:00", end: "22:00" }],
    tuesday: [{ start: "06:00", end: "22:00" }],
    wednesday: [{ start: "06:00", end: "22:00" }],
    thursday: [{ start: "06:00", end: "22:00" }],
    friday: [{ start: "06:00", end: "22:00" }],
  },
  slot_duration_minutes: 60, active: true, description: null,
};

// ─── Setup hook defaults before each test ─────────────────────────────────────

function setupDefaultMocks() {
  vi.mocked(bookingHooks.useFacilities).mockReturnValue({
    data: { items: [FACILITY], next_cursor: null }, isLoading: false, error: null,
  } as unknown as ReturnType<typeof bookingHooks.useFacilities>);
  vi.mocked(bookingHooks.useFacilityCatalog).mockReturnValue({
    data: { items: CATALOG },
  } as unknown as ReturnType<typeof bookingHooks.useFacilityCatalog>);
  vi.mocked(bookingHooks.useAvailability).mockReturnValue({
    data: { facility_id: "f1", date: "2027-01-15", slots: SLOTS }, isLoading: false,
  } as unknown as ReturnType<typeof bookingHooks.useAvailability>);
  vi.mocked(bookingHooks.useCreateBooking).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof bookingHooks.useCreateBooking>);
  vi.mocked(bookingHooks.useMyBookings).mockReturnValue({
    data: { items: [BOOKING] }, isLoading: false,
  } as unknown as ReturnType<typeof bookingHooks.useMyBookings>);
  vi.mocked(bookingHooks.useCancelBooking).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof bookingHooks.useCancelBooking>);

  vi.mocked(tenantHooks.useFacilityCatalog).mockReturnValue({
    data: { items: CATALOG },
  } as unknown as ReturnType<typeof tenantHooks.useFacilityCatalog>);
  vi.mocked(tenantHooks.useTenantFacilities).mockReturnValue({
    data: { items: [ACTIVE_FAC] }, isLoading: false,
  } as unknown as ReturnType<typeof tenantHooks.useTenantFacilities>);
  vi.mocked(tenantHooks.useCreateFacility).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useCreateFacility>);
  vi.mocked(tenantHooks.useUpdateFacility).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useUpdateFacility>);
  vi.mocked(tenantHooks.useDeactivateFacility).mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useDeactivateFacility>);
  vi.mocked(tenantHooks.useTenantUsers).mockReturnValue({
    data: { items: [TENANT_USER] }, isLoading: false,
  } as unknown as ReturnType<typeof tenantHooks.useTenantUsers>);
  vi.mocked(tenantHooks.useCreateTenantUser).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useCreateTenantUser>);
  vi.mocked(tenantHooks.useDeactivateTenantUser).mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useDeactivateTenantUser>);
  vi.mocked(tenantHooks.useResetTenantUserPassword).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useResetTenantUserPassword>);
  vi.mocked(tenantHooks.useBulkCreateUsers).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useBulkCreateUsers>);
  vi.mocked(tenantHooks.useUpdatePolicies).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useUpdatePolicies>);
  vi.mocked(tenantHooks.useUpdateBranding).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof tenantHooks.useUpdateBranding>);

  vi.mocked(adminHooks.useTenants).mockReturnValue({
    data: { items: [TENANT] }, isLoading: false, error: null,
  } as unknown as ReturnType<typeof adminHooks.useTenants>);
  vi.mocked(adminHooks.useCreateTenant).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof adminHooks.useCreateTenant>);
  vi.mocked(adminHooks.useCreateUser).mockReturnValue({
    mutateAsync: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof adminHooks.useCreateUser>);

  vi.mocked(agentHooks.useAgentSendMessage).mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof agentHooks.useAgentSendMessage>);
  vi.mocked(agentHooks.useAgentConfirm).mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof agentHooks.useAgentConfirm>);
  vi.mocked(agentHooks.errorMessageFor).mockReturnValue("Error");
}

// ─── Render helpers ───────────────────────────────────────────────────────────

function withQC(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function withQCRoute(ui: React.ReactElement, path: string, pattern: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── Mode helpers ─────────────────────────────────────────────────────────────

function setMode(mode: "light" | "dark") {
  document.documentElement.setAttribute("data-mode", mode);
}
function clearMode() {
  document.documentElement.removeAttribute("data-mode");
}

let axeResult: Awaited<ReturnType<typeof axe>>;

// ─── STEP 2: Automated axe-core scan ─────────────────────────────────────────

describe("Automated axe-core scan — all key pages, light + dark mode", () => {
  beforeEach(() => {
    setupDefaultMocks();
  });
  afterEach(() => {
    clearMode();
  });

  it("SignIn — no violations (light)", async () => {
    const { container } = render(withQC(<SignIn />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("SignIn — no violations (dark)", async () => {
    const { container } = render(withQC(<SignIn />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Facilities — no violations (light)", async () => {
    const { container } = render(withQC(<Facilities />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Facilities — no violations (dark)", async () => {
    const { container } = render(withQC(<Facilities />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("FacilityAvailability — no violations (light)", async () => {
    const { container } = render(
      withQCRoute(<FacilityAvailability />, "/facilities/f1", "/facilities/:facilityId"),
    );
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("FacilityAvailability — no violations (dark)", async () => {
    const { container } = render(
      withQCRoute(<FacilityAvailability />, "/facilities/f1", "/facilities/:facilityId"),
    );
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("MyBookings — no violations (light)", async () => {
    const { container } = render(withQC(<MyBookings />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("MyBookings — no violations (dark)", async () => {
    const { container } = render(withQC(<MyBookings />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Account — no violations (light)", async () => {
    const { container } = render(withQC(<Account />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Account — no violations (dark)", async () => {
    const { container } = render(withQC(<Account />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Assistant — no violations (light)", async () => {
    const { container } = render(withQC(<Assistant />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("Assistant — no violations (dark)", async () => {
    const { container } = render(withQC(<Assistant />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantDashboard — no violations (light)", async () => {
    const { container } = render(withQC(<TenantDashboard />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantDashboard — no violations (dark)", async () => {
    const { container } = render(withQC(<TenantDashboard />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantFacilities — no violations (light)", async () => {
    const { container } = render(withQC(<TenantFacilities />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantFacilities — no violations (dark)", async () => {
    const { container } = render(withQC(<TenantFacilities />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantUsers — no violations (light)", async () => {
    const { container } = render(withQC(<TenantUsers />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantUsers — no violations (dark)", async () => {
    const { container } = render(withQC(<TenantUsers />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantPolicies — no violations (light)", async () => {
    const { container } = render(withQC(<TenantPolicies />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantPolicies — no violations (dark)", async () => {
    const { container } = render(withQC(<TenantPolicies />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantBranding — no violations (light)", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><TenantBranding /></MemoryRouter>
      </QueryClientProvider>,
    );
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantBranding — no violations (dark)", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><TenantBranding /></MemoryRouter>
      </QueryClientProvider>,
    );
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantList (admin) — no violations (light)", async () => {
    const { container } = render(withQC(<TenantList />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("TenantList (admin) — no violations (dark)", async () => {
    const { container } = render(withQC(<TenantList />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("CreateTenant (admin) — no violations (light)", async () => {
    const { container } = render(withQC(<CreateTenant />));
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("CreateTenant (admin) — no violations (dark)", async () => {
    const { container } = render(withQC(<CreateTenant />));
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("CreateUser (admin) — no violations (light)", async () => {
    const { container } = render(
      withQCRoute(
        <CreateUser />,
        "/admin/tenants/t-1/users/new",
        "/admin/tenants/:tenantId/users/new",
      ),
    );
    setMode("light");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });

  it("CreateUser (admin) — no violations (dark)", async () => {
    const { container } = render(
      withQCRoute(
        <CreateUser />,
        "/admin/tenants/t-1/users/new",
        "/admin/tenants/:tenantId/users/new",
      ),
    );
    setMode("dark");
    axeResult = await axe(container);
    expect(axeResult).toHaveNoViolations();
  });
});

// ─── STEP 3: Keyboard navigation ──────────────────────────────────────────────

describe("Keyboard navigation — key interactive flows", () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  it("SignIn form: Tab reaches email → password → show/hide → submit → Google → forgot-pw", async () => {
    const user = userEvent.setup();
    render(withQC(<SignIn />));

    await user.tab();
    expect(document.activeElement).toHaveAttribute("id", "sign-in-email");

    await user.tab();
    expect(document.activeElement).toHaveAttribute("id", "sign-in-password");

    await user.tab();
    // Show/hide password toggle button
    expect(document.activeElement).toHaveAttribute("aria-label");
    const ariaLabel = document.activeElement?.getAttribute("aria-label") ?? "";
    expect(ariaLabel).toMatch(/show|hide password/i);

    await user.tab();
    expect(document.activeElement).toHaveAttribute("type", "submit");

    await user.tab();
    // Google button (outline variant, no type attr defaults to button)
    expect(document.activeElement?.tagName).toBe("BUTTON");
    expect(document.activeElement?.textContent).toMatch(/google/i);

    await user.tab();
    // Forgot-password link
    expect(document.activeElement?.tagName).toBe("A");
    expect(document.activeElement?.textContent).toMatch(/forgot/i);
  });

  it("Facilities grid: Tab reaches each facility link; Enter navigates", async () => {
    const user = userEvent.setup();
    render(withQC(<Facilities />));

    const facilityLink = screen.getByRole("link", { name: /Tennis Court A/i });
    await user.tab();
    // At least one tab should land on the facility link
    let found = false;
    for (let i = 0; i < 10; i++) {
      if (document.activeElement === facilityLink) { found = true; break; }
      await user.tab();
    }
    expect(found).toBe(true);
  });

  it("FacilityAvailability: date input and slot buttons are keyboard reachable", async () => {
    const user = userEvent.setup();
    render(
      withQCRoute(<FacilityAvailability />, "/facilities/f1", "/facilities/:facilityId"),
    );

    const dateInput = screen.getByLabelText("Date");
    const availableSlot = screen.getByRole("button", { name: /08:00/ });
    const bookedSlot = screen.getByRole("button", { name: /09:00/ });

    // Tab through elements; verify date input and available slot are reachable
    let foundDate = false;
    let foundAvailable = false;
    for (let i = 0; i < 15; i++) {
      await user.tab();
      if (document.activeElement === dateInput) foundDate = true;
      if (document.activeElement === availableSlot) foundAvailable = true;
    }
    expect(foundDate).toBe(true);
    expect(foundAvailable).toBe(true);

    // Booked slot is disabled — cannot be focused by Tab (browser skips disabled)
    expect(bookedSlot).toBeDisabled();
  });

  it("Account form: Tab reaches both password fields and submit button", async () => {
    const user = userEvent.setup();
    render(withQC(<Account />));

    const newPw = screen.getByLabelText("New password");
    const confirmPw = screen.getByLabelText("Confirm new password");
    const submitBtn = screen.getByRole("button", { name: /change password/i });

    let foundNew = false, foundConfirm = false, foundSubmit = false;
    for (let i = 0; i < 10; i++) {
      await user.tab();
      if (document.activeElement === newPw) foundNew = true;
      if (document.activeElement === confirmPw) foundConfirm = true;
      if (document.activeElement === submitBtn) foundSubmit = true;
    }
    expect(foundNew).toBe(true);
    expect(foundConfirm).toBe(true);
    expect(foundSubmit).toBe(true);
  });

  it("MyBookings: Cancel button is keyboard reachable and operable", async () => {
    const user = userEvent.setup();
    render(withQC(<MyBookings />));

    const cancelBtn = screen.getByRole("button", { name: /cancel/i });
    let found = false;
    for (let i = 0; i < 10; i++) {
      await user.tab();
      if (document.activeElement === cancelBtn) { found = true; break; }
    }
    expect(found).toBe(true);

    // Pressing Enter/Space on cancel button should open the dialog
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

// ─── STEP 4: ConfirmDialog focus-trap verification ────────────────────────────

describe("ConfirmDialog — focus trap, Escape close, return focus", () => {
  it("focus moves into dialog when opened", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <ConfirmDialog
        title="Remove item"
        body={<p>Are you sure?</p>}
        confirmLabel="Remove"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    // Wait a tick for Radix FocusScope to move focus into dialog
    await act(async () => {});

    // Focus should be inside the dialog
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("Tab cycles inside dialog without escaping", async () => {
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        title="Remove"
        body={<p>Sure?</p>}
        confirmLabel="Remove"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const dialog = screen.getByRole("dialog");
    await act(async () => {});

    // Tab 10 times — every focused element must remain inside dialog
    for (let i = 0; i < 10; i++) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("Escape closes dialog and calls onCancel", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        title="Remove"
        body={<p>Sure?</p>}
        confirmLabel="Remove"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await act(async () => {});
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("Cancel button keystroke calls onCancel", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        title="Remove"
        body={<p>Sure?</p>}
        confirmLabel="Remove"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await act(async () => {});

    // Tab to Cancel button and activate it
    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    cancelBtn.focus();
    await user.keyboard("{Enter}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("Confirm button is operable via keyboard", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        title="Remove"
        body={<p>Sure?</p>}
        confirmLabel="Remove"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await act(async () => {});

    const confirmBtn = screen.getByRole("button", { name: "Remove" });
    confirmBtn.focus();
    await user.keyboard("{Enter}");
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

// ─── STEP 5: SlotGrid accessible states ──────────────────────────────────────

describe("SlotGrid — accessible name/role per state (not color/text-only)", () => {
  it("available slot: button with accessible name including time and 'available'", () => {
    render(<SlotGrid slots={SLOTS} onPick={vi.fn()} />);
    const availBtn = screen.getByRole("button", { name: /08:00.*available/i });
    expect(availBtn).toBeInTheDocument();
    expect(availBtn).not.toBeDisabled();
  });

  it("booked slot: disabled button with accessible name including time and 'booked'", () => {
    render(<SlotGrid slots={SLOTS} onPick={vi.fn()} />);
    const bookedBtn = screen.getByRole("button", { name: /09:00.*booked/i });
    expect(bookedBtn).toBeInTheDocument();
    expect(bookedBtn).toBeDisabled();
  });

  it("past slot: disabled button with accessible name including time and 'past'", () => {
    render(<SlotGrid slots={SLOTS} onPick={vi.fn()} />);
    const pastBtn = screen.getByRole("button", { name: /06:00.*past/i });
    expect(pastBtn).toBeInTheDocument();
    expect(pastBtn).toBeDisabled();
  });

  it("slot state is not color-only: text label present for each state", () => {
    render(<SlotGrid slots={SLOTS} onPick={vi.fn()} />);
    expect(screen.getByText("available")).toBeInTheDocument();
    expect(screen.getByText("booked")).toBeInTheDocument();
    expect(screen.getByText("past")).toBeInTheDocument();
  });

  it("axe: SlotGrid has no violations", async () => {
    const { container } = render(<SlotGrid slots={SLOTS} onPick={vi.fn()} />);
    const result = await axe(container);
    expect(result).toHaveNoViolations();
  });

  it("axe: ConfirmDialog has no violations", async () => {
    const { container } = render(
      <ConfirmDialog
        title="Delete"
        body={<p>Are you sure?</p>}
        confirmLabel="Delete"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const result = await axe(container);
    expect(result).toHaveNoViolations();
  });
});
