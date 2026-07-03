import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useInstallPrompt", () => ({
  useInstallPrompt: vi.fn(),
}));

import * as hook from "../hooks/useInstallPrompt";
import { InstallPrompt } from "./InstallPrompt";

beforeEach(() => localStorage.clear());
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });

describe("InstallPrompt — hidden / dismissed", () => {
  it("renders nothing when state is hidden (standalone)", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "hidden" });
    const { container } = render(<InstallPrompt />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when dismiss key is already set in localStorage", () => {
    localStorage.setItem("slotsense-install-dismissed", "1");
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "manual-hint" });
    const { container } = render(<InstallPrompt />);
    expect(container.firstChild).toBeNull();
  });
});

describe("InstallPrompt — manual-hint (no native prompt yet)", () => {
  it("shows install button by default", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "manual-hint" });
    render(<InstallPrompt />);
    expect(screen.getByRole("button", { name: "Install app" })).toBeInTheDocument();
    expect(screen.getByText(/Install SlotSense/i)).toBeInTheDocument();
  });

  it("reveals ⋮ instructions after tapping Install", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "manual-hint" });
    render(<InstallPrompt />);
    fireEvent.click(screen.getByRole("button", { name: "Install app" }));
    expect(screen.getByText("⋮ menu")).toBeInTheDocument();
    expect(screen.getByText("Install app")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Install app" })).not.toBeInTheDocument();
  });

  it("dismiss button persists dismissal to localStorage and hides banner", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "manual-hint" });
    const { container } = render(<InstallPrompt />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(localStorage.getItem("slotsense-install-dismissed")).toBe("1");
    expect(container.firstChild).toBeNull();
  });
});

describe("InstallPrompt — ios-hint", () => {
  it("shows Share → Add to Home Screen instructions immediately", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "ios-hint" });
    render(<InstallPrompt />);
    expect(screen.getByText("Share")).toBeInTheDocument();
    expect(screen.getByText("Add to Home Screen")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Install app" })).not.toBeInTheDocument();
  });

  it("dismiss button hides the banner and persists to localStorage", () => {
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "ios-hint" });
    const { container } = render(<InstallPrompt />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(localStorage.getItem("slotsense-install-dismissed")).toBe("1");
    expect(container.firstChild).toBeNull();
  });
});

describe("InstallPrompt — ready (native prompt available)", () => {
  it("shows install button", () => {
    const mockPrompt = vi.fn();
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "ready", prompt: mockPrompt });
    render(<InstallPrompt />);
    expect(screen.getByRole("button", { name: "Install app" })).toBeInTheDocument();
  });

  it("calls state.prompt() when Install button is clicked", () => {
    const mockPrompt = vi.fn();
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "ready", prompt: mockPrompt });
    render(<InstallPrompt />);
    fireEvent.click(screen.getByRole("button", { name: "Install app" }));
    expect(mockPrompt).toHaveBeenCalledTimes(1);
  });

  it("dismiss button persists to localStorage and hides banner", () => {
    const mockPrompt = vi.fn();
    vi.mocked(hook.useInstallPrompt).mockReturnValue({ kind: "ready", prompt: mockPrompt });
    const { container } = render(<InstallPrompt />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(localStorage.getItem("slotsense-install-dismissed")).toBe("1");
    expect(container.firstChild).toBeNull();
  });
});
