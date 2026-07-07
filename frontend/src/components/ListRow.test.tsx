import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ListRow } from "./ListRow";

describe("ListRow", () => {
  it("renders children and action", () => {
    render(
      <ListRow action={<button>Act</button>}>
        <span>Content</span>
      </ListRow>,
    );
    expect(screen.getByText("Content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });

  it("outer wrapper stacks on mobile (flex-col) and rows at sm+ (sm:flex-row)", () => {
    const { container } = render(
      <ListRow action={<button>Act</button>}>
        <span>Content</span>
      </ListRow>,
    );
    const outer = container.firstElementChild as HTMLElement;
    expect(outer.className).toMatch(/flex-col/);
    expect(outer.className).toMatch(/sm:flex-row/);
    expect(outer.className).toMatch(/sm:items-center/);
    expect(outer.className).toMatch(/sm:justify-between/);
  });

  it("action container wraps (flex-wrap) and shrinks only at sm+ (sm:shrink-0)", () => {
    const { container } = render(
      <ListRow action={<button>Act</button>}>
        <span>Content</span>
      </ListRow>,
    );
    // Action container is the second child of the outer wrapper
    const actionContainer = container.firstElementChild?.children[1] as HTMLElement;
    expect(actionContainer.className).toMatch(/flex-wrap/);
    expect(actionContainer.className).toMatch(/sm:shrink-0/);
    // Must NOT have the old non-responsive shrink-0 (which would force action to fixed-width on mobile)
    expect(actionContainer.className).not.toMatch(/(?<![:\w])shrink-0(?!\w)/);
  });

  it("renders without action when action prop is omitted", () => {
    const { container } = render(<ListRow><span>Only content</span></ListRow>);
    expect(screen.getByText("Only content")).toBeInTheDocument();
    // No action container rendered
    expect(container.firstElementChild?.children.length).toBe(1);
  });

  it("merges className and actionClassName overrides", () => {
    const { container } = render(
      <ListRow className="custom-outer" actionClassName="custom-action" action={<button>Act</button>}>
        <span>Content</span>
      </ListRow>,
    );
    const outer = container.firstElementChild as HTMLElement;
    expect(outer.className).toContain("custom-outer");
    const actionContainer = outer.children[1] as HTMLElement;
    expect(actionContainer.className).toContain("custom-action");
  });
});
