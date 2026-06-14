import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../lib/api";
import { useCreateUser } from "../../hooks/adminHooks";
import CreateUser from "./CreateUser";

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

vi.mock("../../hooks/adminHooks", () => ({
  useCreateUser: vi.fn(),
}));

function renderCreate(search = "") {
  return render(
    <MemoryRouter initialEntries={[`/admin/tenants/t-1/users/new${search}`]}>
      <Routes>
        <Route path="/admin/tenants/:tenantId/users/new" element={<CreateUser />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(useCreateUser).mockImplementation(
    () => ({ mutateAsync: vi.fn().mockResolvedValue({ uid: "u-1", temp_password: "TempP@ss99" }), isPending: false }) as unknown as ReturnType<typeof useCreateUser>,
  );
});

describe("CreateUser", () => {
  it("shows temp-password block with warning and copy button after success", async () => {
    const user = userEvent.setup();
    renderCreate();

    // textbox inputs in DOM order: email, displayName, flat
    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "alice@test.com");
    await user.type(inputs[1], "Alice Smith");
    await user.type(inputs[2], "A-101");

    await user.click(screen.getByRole("button", { name: /create user/i }));

    await waitFor(() => {
      expect(screen.getByText(/shown only once/i)).toBeInTheDocument();
    });
    expect(document.body).toHaveTextContent("TempP@ss99");
    expect(screen.getByRole("button", { name: /copy credentials/i })).toBeInTheDocument();
  });

  it("defaults role to tenant_admin when ?first=1", () => {
    renderCreate("?first=1");
    const select = screen.getByRole("combobox");
    expect((select as HTMLSelectElement).value).toBe("tenant_admin");
  });

  it("shows catalog error message on USER_EMAIL_TAKEN failure", async () => {
    vi.mocked(useCreateUser).mockImplementation(
      () => ({ mutateAsync: vi.fn().mockRejectedValue(
        new ApiClientError({ code: "USER_EMAIL_TAKEN", message: "Email taken", status: 409 }),
      ), isPending: false }) as unknown as ReturnType<typeof useCreateUser>,
    );

    const user = userEvent.setup();
    renderCreate();

    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "dup@test.com");
    await user.type(inputs[1], "Dup User");
    await user.type(inputs[2], "B-202");

    await user.click(screen.getByRole("button", { name: /create user/i }));

    await waitFor(() => {
      expect(screen.getByText(/already registered/i)).toBeInTheDocument();
    });
  });
});
