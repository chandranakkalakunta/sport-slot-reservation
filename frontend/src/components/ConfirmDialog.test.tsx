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

  // ── Phase 13.2: confirmationPhrase prop ─────────────────────────────────────

  it("(e) backward-compat: confirm button enabled when busy=false and no confirmationPhrase", () => {
    // Existing callers that omit confirmationPhrase must behave identically to before.
    renderDialog({ busy: false });
    expect(screen.getByRole("button", { name: "Delete" })).not.toBeDisabled();
  });

  it("(d) with confirmationPhrase: renders a text input with phrase in label", () => {
    // RED: ConfirmDialog does not yet accept confirmationPhrase → input absent.
    renderDialog({ confirmationPhrase: "DELETE" });
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByText(/Type DELETE to confirm/i)).toBeInTheDocument();
  });

  it("(d) with confirmationPhrase: confirm button disabled when input is empty", () => {
    renderDialog({ confirmationPhrase: "DELETE" });
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });

  it("(d) with confirmationPhrase: confirm button disabled when input does not match", async () => {
    renderDialog({ confirmationPhrase: "DELETE" });
    await userEvent.type(screen.getByRole("textbox"), "del");
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });

  it("(d) with confirmationPhrase: confirm button enabled only on exact match", async () => {
    renderDialog({ confirmationPhrase: "DELETE" });
    await userEvent.type(screen.getByRole("textbox"), "DELETE");
    expect(screen.getByRole("button", { name: "Delete" })).not.toBeDisabled();
  });

  it("(d) with confirmationPhrase: confirm button re-disabled after clearing typed value", async () => {
    renderDialog({ confirmationPhrase: "DELETE" });
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "DELETE");
    expect(screen.getByRole("button", { name: "Delete" })).not.toBeDisabled();
    await userEvent.clear(input);
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });
});
