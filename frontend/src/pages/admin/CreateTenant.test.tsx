import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// No importOriginal — avoids loading real adminHooks → api.ts → firebase.ts
vi.mock("../../hooks/adminHooks", () => ({
  useCreateTenant: vi.fn(),
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

import { useCreateTenant } from "../../hooks/adminHooks";
import CreateTenant from "./CreateTenant";

function renderPage() {
  return render(<MemoryRouter><CreateTenant /></MemoryRouter>);
}

describe("CreateTenant", () => {
  beforeEach(() => {
    vi.mocked(useCreateTenant).mockImplementation(
      () => ({
        mutateAsync: vi.fn().mockResolvedValue({ tenant_id: "t-new" }),
        isPending: false,
      }) as unknown as ReturnType<typeof useCreateTenant>,
    );
  });

  it("renders the New tenant heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "New tenant" })).toBeInTheDocument();
  });

  it("renders the Create tenant button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /create tenant/i })).toBeInTheDocument();
  });

  it("shows fallback error message on unexpected failure", async () => {
    vi.mocked(useCreateTenant).mockImplementation(
      () => ({
        // Reject with a plain Error (not ApiClientError) → fallback message fires
        mutateAsync: vi.fn().mockRejectedValue(new Error("network")),
        isPending: false,
      }) as unknown as ReturnType<typeof useCreateTenant>,
    );

    const user = userEvent.setup();
    renderPage();

    const inputs = screen.getAllByRole("textbox");
    await user.type(inputs[0], "oakwood");
    await user.type(inputs[1], "Oakwood Residency");
    await user.click(screen.getByRole("button", { name: /create tenant/i }));

    await waitFor(() => {
      expect(screen.getByText("Failed to create tenant.")).toBeInTheDocument();
    });
  });
});
