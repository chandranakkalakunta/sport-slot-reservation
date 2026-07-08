import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ResidentNav } from "./ResidentNav";

function wrap() {
  return render(
    <MemoryRouter>
      <ResidentNav />
    </MemoryRouter>,
  );
}

describe("ResidentNav", () => {
  it("renders a Facilities link pointing to /", () => {
    wrap();
    expect(screen.getByRole("link", { name: "Facilities" })).toHaveAttribute("href", "/");
  });

  it("renders a My bookings link pointing to /bookings", () => {
    wrap();
    expect(screen.getByRole("link", { name: "My bookings" })).toHaveAttribute("href", "/bookings");
  });

  it("renders both links at once — neither is a dead end", () => {
    wrap();
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });
});
