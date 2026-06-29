import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

function renderDialog(overrides: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const props = {
    title: "Delete item",
    body: <p>Are you sure you want to delete this?</p>,
    confirmLabel: "Delete",
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    busy: false,
    ...overrides,
  };
  render(<ConfirmDialog {...props} />);
  return props;
}

describe("ConfirmDialog", () => {
  it("renders with dialog role", () => {
    renderDialog();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders title and body content", () => {
    renderDialog();
    expect(screen.getByText("Delete item")).toBeInTheDocument();
    expect(screen.getByText("Are you sure you want to delete this?")).toBeInTheDocument();
  });

  it("renders confirm button with confirmLabel", () => {
    renderDialog({ confirmLabel: "Remove" });
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("renders cancel button", () => {
    renderDialog();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button clicked", async () => {
    const props = renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(props.onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when cancel button clicked", async () => {
    const props = renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onCancel).toHaveBeenCalledOnce();
  });

  it("disables buttons and shows ellipsis on confirm when busy", () => {
    renderDialog({ busy: true });
    expect(screen.getByRole("button", { name: "…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("uses defaultConfirmLabel when none provided", () => {
    renderDialog({ confirmLabel: undefined });
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });
});
