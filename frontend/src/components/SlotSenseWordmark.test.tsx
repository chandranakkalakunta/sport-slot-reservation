import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SlotSenseWordmark } from "./SlotSenseWordmark";

// No hooks, no firebase chain — plain render test.

describe("SlotSenseWordmark", () => {
  it("renders visible 'SlotSense' text", () => {
    render(<SlotSenseWordmark />);
    expect(screen.getByText("SlotSense")).toBeInTheDocument();
  });

  it("accepts an optional className prop", () => {
    const { container } = render(<SlotSenseWordmark className="text-xs" />);
    expect(container.firstChild).toHaveClass("text-xs");
  });
});
