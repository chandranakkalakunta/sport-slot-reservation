import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ClaimsErrorFallback } from "./ClaimsErrorFallback";

describe("ClaimsErrorFallback", () => {
  it("renders the informational message and Retry button", () => {
    render(<ClaimsErrorFallback onRetry={vi.fn().mockResolvedValue(undefined)} />);
    expect(screen.getByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("calls onRetry when Retry is clicked", async () => {
    const onRetry = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ClaimsErrorFallback onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows 'Retrying…' while onRetry is pending and re-enables after", async () => {
    let resolve!: () => void;
    const onRetry = vi.fn().mockReturnValue(new Promise<void>((res) => { resolve = res; }));
    const user = userEvent.setup();
    render(<ClaimsErrorFallback onRetry={onRetry} />);

    await user.click(screen.getByRole("button", { name: /retry/i }));
    // While pending: button is disabled and shows "Retrying…"
    expect(screen.getByRole("button", { name: /retrying/i })).toBeDisabled();

    // Resolve the promise
    resolve();
    // After resolve: button re-enables
    expect(await screen.findByRole("button", { name: /retry/i })).not.toBeDisabled();
  });
});
