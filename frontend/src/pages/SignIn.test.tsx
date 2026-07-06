import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    signIn: vi.fn(),
    signInWithGoogle: vi.fn(),
  }),
}));

import SignIn from "./SignIn";

function renderPage() {
  return render(
    <MemoryRouter>
      <SignIn />
    </MemoryRouter>,
  );
}

describe("SignIn", () => {
  it("renders the branded heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "SlotSense" })).toBeInTheDocument();
  });

  it("renders the email input", () => {
    renderPage();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders the password input", () => {
    renderPage();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("renders the sign-in submit button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("renders the forgot-password link", () => {
    renderPage();
    expect(screen.getByRole("link", { name: "Forgot password?" })).toBeInTheDocument();
  });

  it("renders the Google sign-in button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
  });

  // ── Phase 13.7 banner tests ──────────────────────────────────────────────

  it("does NOT show redirect banner when no ?redirected param", () => {
    render(<MemoryRouter initialEntries={["/signin"]}><SignIn /></MemoryRouter>);
    expect(
      screen.queryByText(/redirected to your community/i),
    ).not.toBeInTheDocument();
  });

  it("shows redirect banner when ?redirected=1 is present", () => {
    render(
      <MemoryRouter initialEntries={["/signin?redirected=1"]}>
        <SignIn />
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/redirected to your community/i),
    ).toBeInTheDocument();
  });

  it("does NOT show banner for ?redirected=0 or other values", () => {
    render(
      <MemoryRouter initialEntries={["/signin?redirected=0"]}>
        <SignIn />
      </MemoryRouter>,
    );
    expect(
      screen.queryByText(/redirected to your community/i),
    ).not.toBeInTheDocument();
  });
});
