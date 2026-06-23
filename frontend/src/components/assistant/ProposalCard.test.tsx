import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProposalCard } from "./ProposalCard";

const SUMMARY_BOOK = {
  action_type: "book" as const,
  facility_name: "Tennis Court 1",
  sport: "tennis",
  date: "2026-07-01",
  start: "09:00",
  end: "10:00",
  facility_id: "fac-1",
};

const SUMMARY_CANCEL = {
  action_type: "cancel" as const,
  facility_name: "Tennis Court 1",
  sport: "tennis",
  date: "2026-07-01",
  start: "09:00",
  end: "10:00",
  booking_id: "bk-1",
};

afterEach(() => { vi.useRealTimers(); });

describe("ProposalCard", () => {
  it("renders booking proposal summary fields", () => {
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={Date.now()}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      isConfirming={false}
    />);
    expect(screen.getByText("Booking proposal")).toBeInTheDocument();
    expect(screen.getByText("Tennis Court 1")).toBeInTheDocument();
    expect(screen.getByText("tennis")).toBeInTheDocument();
    expect(screen.getByText("2026-07-01")).toBeInTheDocument();
    expect(screen.getByText(/9:00 AM/)).toBeInTheDocument();
  });

  it("renders cancellation proposal heading for cancel action_type", () => {
    render(<ProposalCard
      summary={SUMMARY_CANCEL}
      timestamp={Date.now()}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      isConfirming={false}
    />);
    expect(screen.getByText("Cancellation proposal")).toBeInTheDocument();
  });

  it("calls onConfirm when Confirm clicked", async () => {
    const onConfirm = vi.fn();
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={Date.now()}
      onConfirm={onConfirm}
      onCancel={vi.fn()}
      isConfirming={false}
    />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when Cancel clicked", async () => {
    const onCancel = vi.fn();
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={Date.now()}
      onConfirm={vi.fn()}
      onCancel={onCancel}
      isConfirming={false}
    />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("shows expired message and hides buttons after 5-min timer fires", () => {
    vi.useFakeTimers();
    const ts = Date.now();
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={ts}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      isConfirming={false}
    />);
    act(() => { vi.advanceTimersByTime(5 * 60 * 1000 + 100); });
    expect(screen.getByText(/proposal has expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("shows already-expired state when timestamp is older than 5 min", () => {
    const oldTs = Date.now() - 6 * 60 * 1000;
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={oldTs}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      isConfirming={false}
    />);
    expect(screen.getByText(/proposal has expired/i)).toBeInTheDocument();
  });

  it("shows confirming state and disables button when isConfirming is true", () => {
    render(<ProposalCard
      summary={SUMMARY_BOOK}
      timestamp={Date.now()}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      isConfirming={true}
    />);
    expect(screen.getByRole("button", { name: /confirming/i })).toBeDisabled();
  });
});
