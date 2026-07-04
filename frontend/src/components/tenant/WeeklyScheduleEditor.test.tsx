import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DAY_ORDER, type WeeklySchedule } from "../../types/facilitySchedule";
import { emptyWeeklySchedule, WeeklyScheduleEditor } from "./WeeklyScheduleEditor";

function makeSchedule(overrides: Partial<WeeklySchedule> = {}): WeeklySchedule {
  return { ...emptyWeeklySchedule(), ...overrides };
}

describe("WeeklyScheduleEditor", () => {
  it("renders all 7 days", () => {
    render(<WeeklyScheduleEditor value={emptyWeeklySchedule()} onChange={() => {}} />);
    for (const day of DAY_ORDER) {
      expect(screen.getByText(day)).toBeInTheDocument();
    }
  });

  it("shows range summary for a day with ranges", () => {
    const value = makeSchedule({ tuesday: [{ start: "08:00", end: "12:00" }] });
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);
    expect(screen.getByText("08:00–12:00")).toBeInTheDocument();
  });

  it("shows 'Closed' for a day with no ranges", () => {
    render(<WeeklyScheduleEditor value={emptyWeeklySchedule()} onChange={() => {}} />);
    const closedItems = screen.getAllByText("Closed");
    expect(closedItems.length).toBe(7);
  });

  it("Monday dialog opens empty even when other days have ranges", async () => {
    const value = makeSchedule({
      sunday: [{ start: "07:00", end: "19:00" }],
    });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit monday hours/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton")).toBeNull();
    // No time inputs should be present — dialog opened empty
    expect(screen.queryAllByDisplayValue(/\d{2}:\d{2}/).length).toBe(0);
    expect(screen.getByText(/no ranges/i)).toBeInTheDocument();
  });

  it("non-Monday empty day pre-fills from previous day's ranges", async () => {
    const value = makeSchedule({
      monday: [{ start: "06:00", end: "10:00" }],
    });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit tuesday hours/i }));

    const dialog = screen.getByRole("dialog");
    // Pre-filled with Monday's range as editable inputs
    const startInputs = within(dialog).getAllByLabelText(/start/i);
    const endInputs = within(dialog).getAllByLabelText(/end/i);
    expect(startInputs[0]).toHaveValue("06:00");
    expect(endInputs[0]).toHaveValue("10:00");
  });

  it("opening a day that already has ranges shows ITS ranges, not carry-forward", async () => {
    const value = makeSchedule({
      monday: [{ start: "05:00", end: "09:00" }],
      tuesday: [{ start: "14:00", end: "18:00" }],
    });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit tuesday hours/i }));

    const dialog = screen.getByRole("dialog");
    const startInputs = within(dialog).getAllByLabelText(/start/i);
    expect(startInputs[0]).toHaveValue("14:00");
  });

  it("Add range button appends a new row", async () => {
    const value = makeSchedule({ wednesday: [{ start: "08:00", end: "12:00" }] });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit wednesday hours/i }));

    const dialog = screen.getByRole("dialog");
    const beforeCount = within(dialog).getAllByLabelText(/start/i).length;
    await user.click(within(dialog).getByRole("button", { name: /add range/i }));
    const afterCount = within(dialog).getAllByLabelText(/start/i).length;
    expect(afterCount).toBe(beforeCount + 1);
  });

  it("Remove range button removes the correct row", async () => {
    const value = makeSchedule({
      thursday: [
        { start: "06:00", end: "10:00" },
        { start: "14:00", end: "18:00" },
      ],
    });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit thursday hours/i }));

    const dialog = screen.getByRole("dialog");
    const removeButtons = within(dialog).getAllByRole("button", { name: /remove range/i });
    expect(removeButtons.length).toBe(2);

    await user.click(removeButtons[0]);
    expect(within(dialog).getAllByLabelText(/start/i).length).toBe(1);
    expect(within(dialog).getAllByLabelText(/start/i)[0]).toHaveValue("14:00");
  });

  it("start >= end disables Save and shows an error", async () => {
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={emptyWeeklySchedule()} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit friday hours/i }));

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /add range/i }));

    const startInput = within(dialog).getAllByLabelText(/start/i)[0];
    const endInput = within(dialog).getAllByLabelText(/end/i)[0];
    await user.clear(startInput);
    await user.type(startInput, "12:00");
    await user.clear(endInput);
    await user.type(endInput, "08:00");

    expect(within(dialog).getByRole("button", { name: /^save$/i })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: /^save$/i }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("overlapping ranges disables Save and shows an error", async () => {
    const value = makeSchedule({
      saturday: [{ start: "06:00", end: "14:00" }],
    });
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={value} onChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit saturday hours/i }));

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /add range/i }));

    const startInputs = within(dialog).getAllByLabelText(/start/i);
    const endInputs = within(dialog).getAllByLabelText(/end/i);
    await user.clear(startInputs[1]);
    await user.type(startInputs[1], "10:00");
    await user.clear(endInputs[1]);
    await user.type(endInputs[1], "18:00");

    expect(within(dialog).getByRole("button", { name: /^save$/i })).toBeDisabled();
  });

  it("Save fires onChange with the correct full-object shape", async () => {
    const schedule = makeSchedule({ sunday: [{ start: "09:00", end: "17:00" }] });
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<WeeklyScheduleEditor value={schedule} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /edit sunday hours/i }));

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /add range/i }));

    const startInputs = within(dialog).getAllByLabelText(/start/i);
    const endInputs = within(dialog).getAllByLabelText(/end/i);
    await user.clear(startInputs[1]);
    await user.type(startInputs[1], "19:00");
    await user.clear(endInputs[1]);
    await user.type(endInputs[1], "22:00");

    await user.click(within(dialog).getByRole("button", { name: /^save$/i }));

    expect(onChange).toHaveBeenCalledOnce();
    const result: WeeklySchedule = onChange.mock.calls[0][0];
    // All 7 days present
    for (const day of DAY_ORDER) {
      expect(result).toHaveProperty(day);
    }
    // Sunday has the new two ranges
    expect(result.sunday).toEqual([
      { start: "09:00", end: "17:00" },
      { start: "19:00", end: "22:00" },
    ]);
    // Other days unchanged
    expect(result.monday).toEqual([]);
  });
});
