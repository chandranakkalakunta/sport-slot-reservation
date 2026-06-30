import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SuggestedPrompts } from "./SuggestedPrompts";

const EXPECTED_PROMPTS = [
  "Book tennis tomorrow",
  "Is tennis free today?",
  "Is football available tomorrow?",
  "Book badminton this Saturday",
];

describe("SuggestedPrompts", () => {
  it("renders 4 chips with the exact expected text", () => {
    render(<SuggestedPrompts onSelect={vi.fn()} />);
    for (const p of EXPECTED_PROMPTS) {
      expect(screen.getByRole("button", { name: p })).toBeInTheDocument();
    }
  });

  it("calls onSelect with the chip text when a chip is clicked", async () => {
    const onSelect = vi.fn();
    render(<SuggestedPrompts onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: EXPECTED_PROMPTS[1] }));
    expect(onSelect).toHaveBeenCalledWith(EXPECTED_PROMPTS[1]);
  });

  it("calls onSelect with the correct text for each chip", async () => {
    const onSelect = vi.fn();
    render(<SuggestedPrompts onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: EXPECTED_PROMPTS[0] }));
    expect(onSelect).toHaveBeenCalledWith(EXPECTED_PROMPTS[0]);
  });
});
