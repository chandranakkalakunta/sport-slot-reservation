import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

import {
  useBulkCreateUsers, useCreateTenantUser, useDeactivateTenantUser,
  useResetTenantUserPassword, useTenantUsers,
} from "../../hooks/tenantAdminHooks";
import TenantUsers from "./TenantUsers";

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useTenantUsers: vi.fn(),
  useCreateTenantUser: vi.fn(),
  useDeactivateTenantUser: vi.fn(),
  useResetTenantUserPassword: vi.fn(),
  useBulkCreateUsers: vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  ApiClientError: class extends Error {
    code: string; status: number;
    constructor(e: { code: string; message: string; status: number }) {
      super(e.message); this.code = e.code; this.status = e.status;
    }
  },
  apiFetch: vi.fn(),
}));

const USERS = [
  { uid: "u-1", email: "alice@demo.com", display_name: "Alice", role: "resident", flat_number: "A-1", active: true },
];

function renderPage() {
  return render(<MemoryRouter><TenantUsers /></MemoryRouter>);
}

beforeEach(() => {
  vi.mocked(useTenantUsers).mockReturnValue({
    data: { items: USERS }, isLoading: false,
  } as unknown as ReturnType<typeof useTenantUsers>);
  vi.mocked(useCreateTenantUser).mockImplementation(
    () => ({ mutateAsync: vi.fn().mockResolvedValue({ uid: "u-2", temp_password: "NewP@ss1" }), isPending: false }) as unknown as ReturnType<typeof useCreateTenantUser>,
  );
  vi.mocked(useDeactivateTenantUser).mockImplementation(
    () => ({ mutate: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useDeactivateTenantUser>,
  );
  vi.mocked(useResetTenantUserPassword).mockImplementation(
    () => ({ mutateAsync: vi.fn().mockResolvedValue({ uid: "u-1", temp_password: "ResetP@ss1" }), isPending: false }) as unknown as ReturnType<typeof useResetTenantUserPassword>,
  );
  vi.mocked(useBulkCreateUsers).mockImplementation(
    () => ({ mutateAsync: vi.fn(), isPending: false }) as unknown as ReturnType<typeof useBulkCreateUsers>,
  );
});

describe("TenantUsers", () => {
  it("lists active users", () => {
    renderPage();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText(/alice@demo\.com/)).toBeInTheDocument();
  });

  it("add-user form with role=tenant_admin does NOT show flat_number field", async () => {
    const user = userEvent.setup();
    renderPage();

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "tenant_admin");

    expect(screen.queryByLabelText(/flat number/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/A-101/)).not.toBeInTheDocument();
  });

  it("add-user with tenant_admin fires mutation without flat_number", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ uid: "u-3", temp_password: "AdminP@ss1" });
    vi.mocked(useCreateTenantUser).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useCreateTenantUser>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByRole("combobox"), "tenant_admin");
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "newadmin@demo.com");
    await user.type(inputs[1], "New Admin");

    await user.click(screen.getByRole("button", { name: /add user/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ role: "tenant_admin", flat_number: undefined }),
      );
    });
  });

  it("bulk CSV parse+submit calls mutation and renders per-row report", async () => {
    const csvText = "email,display_name,flat_number,role\nok@demo.com,OK,A-1,resident\nbad@demo.com,Bad,A-2,resident\n";
    // jsdom's File doesn't implement .text() — polyfill on Blob.prototype for this test.
    const origText = (Blob.prototype as { text?: unknown }).text;
    (Blob.prototype as { text?: unknown }).text = () => Promise.resolve(csvText);

    const mutateAsync = vi.fn().mockResolvedValue({
      total: 2, created: 1, failed: 1,
      results: [
        { row: 1, email: "ok@demo.com", status: "created", temp_password: "BulkP@ss1" },
        { row: 2, email: "bad@demo.com", status: "failed", reason: "USER_EMAIL_TAKEN" },
      ],
    });
    vi.mocked(useBulkCreateUsers).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useBulkCreateUsers>,
    );
    const user = userEvent.setup();
    renderPage();

    const file = new File([csvText], "users.csv", { type: "text/csv" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ email: "ok@demo.com", role: "resident" }),
        ]),
      );
    });
    expect(screen.getByText(/Total: 2/)).toBeInTheDocument();
    expect(screen.getByText(/USER_EMAIL_TAKEN/)).toBeInTheDocument();

    // Restore
    if (origText === undefined) delete (Blob.prototype as { text?: unknown }).text;
    else (Blob.prototype as { text?: unknown }).text = origText;
  });

  it("reset password button fires mutation and shows CredentialDisplay", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ uid: "u-1", temp_password: "ResetP@ss1" });
    vi.mocked(useResetTenantUserPassword).mockImplementation(
      () => ({ mutateAsync, isPending: false }) as unknown as ReturnType<typeof useResetTenantUserPassword>,
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/ResetP@ss1/)).toBeInTheDocument();
    });
  });
});
