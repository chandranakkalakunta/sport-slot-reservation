import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiFetch: vi.fn(),
  ApiClientError: class ApiClientError extends Error {
    code: string;
    status: number;
    constructor(e: { code: string; message: string; status: number }) {
      super(e.message);
      this.code = e.code;
      this.status = e.status;
    }
  },
}));

import { apiFetch } from "../lib/api";
import ForgotPassword from "./ForgotPassword";

beforeEach(() => {
  vi.mocked(apiFetch).mockReset();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPassword />
    </MemoryRouter>,
  );
}

test("renders email form", () => {
  renderPage();
  expect(screen.getByRole("textbox")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /send reset link/i })).toBeInTheDocument();
});

test("shows neutral confirmation on successful submit", async () => {
  vi.mocked(apiFetch).mockResolvedValueOnce({});
  renderPage();
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "user@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));
  await waitFor(() =>
    expect(screen.getByText(/reset link has been sent/i)).toBeInTheDocument(),
  );
  expect(screen.getByText(/back to sign in/i)).toBeInTheDocument();
});

test("shows identical neutral confirmation when API throws (enumeration-safety)", async () => {
  vi.mocked(apiFetch).mockRejectedValueOnce(new Error("network error"));
  renderPage();
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "notexist@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));
  await waitFor(() =>
    expect(screen.getByText(/reset link has been sent/i)).toBeInTheDocument(),
  );
  // Assert the copy is the same as the success path — no information leaked
  const successMsg = "If an account exists for that email, a reset link has been sent. Check your inbox.";
  expect(screen.getByText(successMsg)).toBeInTheDocument();
});

test("enumeration-safety: success and error confirmation text are identical", async () => {
  const NEUTRAL =
    "If an account exists for that email, a reset link has been sent. Check your inbox.";

  // Success path
  vi.mocked(apiFetch).mockResolvedValueOnce({});
  const { unmount: unmount1 } = renderPage();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "a@b.com" } });
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));
  await waitFor(() => screen.getByText(NEUTRAL));
  const successText = screen.getByText(NEUTRAL).textContent;
  unmount1();

  // Error path
  vi.mocked(apiFetch).mockRejectedValueOnce(new Error("network error"));
  renderPage();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "b@b.com" } });
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));
  await waitFor(() => screen.getByText(NEUTRAL));
  const errorText = screen.getByText(NEUTRAL).textContent;

  expect(successText).toBe(errorText);
});
