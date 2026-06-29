import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { SlotGrid } from "./SlotGrid";
import { type Slot } from "../hooks/bookingHooks";

const slots: Slot[] = [
  { start: "06:00", end: "07:00", status: "available", bookable: true, reason: null },
  { start: "07:00", end: "08:00", status: "booked", bookable: false, reason: "BOOKED" },
];

test("bookable slot fires onPick; booked slot does not", () => {
  const onPick = vi.fn();
  render(<SlotGrid slots={slots} onPick={onPick} />);
  fireEvent.click(screen.getByText("06:00"));
  expect(onPick).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByText("07:00"));
  expect(onPick).toHaveBeenCalledOnce(); // unchanged — booked is disabled
});

test("shows 'available' label on bookable slot", () => {
  render(<SlotGrid slots={slots} onPick={vi.fn()} />);
  expect(screen.getByText("available")).toBeInTheDocument();
});

test("shows reason label on non-bookable slot", () => {
  render(<SlotGrid slots={slots} onPick={vi.fn()} />);
  expect(screen.getByText("booked")).toBeInTheDocument();
});

test("booked slot button is disabled", () => {
  render(<SlotGrid slots={slots} onPick={vi.fn()} />);
  expect(screen.getByRole("button", { name: /07:00/ })).toBeDisabled();
});

test("available slot button is not disabled", () => {
  render(<SlotGrid slots={slots} onPick={vi.fn()} />);
  expect(screen.getByRole("button", { name: /06:00/ })).not.toBeDisabled();
});

test("renders empty message when no slots", () => {
  render(<SlotGrid slots={[]} onPick={vi.fn()} />);
  expect(screen.getByText("No slots available.")).toBeInTheDocument();
});
