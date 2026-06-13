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
