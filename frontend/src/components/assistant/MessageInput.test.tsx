import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe, toHaveNoViolations } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../hooks/useVoiceRecorder", () => ({
  useVoiceRecorder: vi.fn(),
}));

import { useVoiceRecorder } from "../../hooks/useVoiceRecorder";
import { MessageInput } from "./MessageInput";

expect.extend(toHaveNoViolations);

function mockRecorder(overrides: Partial<ReturnType<typeof useVoiceRecorder>> = {}) {
  vi.mocked(useVoiceRecorder).mockReturnValue({
    isSupported: true,
    isRecording: false,
    error: null,
    start: vi.fn().mockResolvedValue(null),
    stop: vi.fn(),
    ...overrides,
  });
}

describe("MessageInput", () => {
  beforeEach(() => {
    mockRecorder();
  });

  it("sends trimmed text and clears the input", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "  book tennis  ");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("book tennis");
    expect(input).toHaveValue("");
  });

  // ── AGENT-UX-02: /clear ────────────────────────────────────────────────────

  it("routes '/clear' to onClear instead of onSend, via Send button", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onClear = vi.fn();
    render(<MessageInput onSend={onSend} onVoice={vi.fn()} onClear={onClear} disabled={false} />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "/clear");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onClear).toHaveBeenCalledOnce();
    expect(onSend).not.toHaveBeenCalled();
    expect(input).toHaveValue("");
  });

  it("routes '/clear' to onClear via Enter key", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onClear = vi.fn();
    render(<MessageInput onSend={onSend} onVoice={vi.fn()} onClear={onClear} disabled={false} />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "/clear{Enter}");

    expect(onClear).toHaveBeenCalledOnce();
    expect(onSend).not.toHaveBeenCalled();
  });

  // ── AGENT-UX-01: up-arrow recall ────────────────────────────────────────────

  it("recalls the last user message on ArrowUp when input is empty", async () => {
    const user = userEvent.setup();
    render(
      <MessageInput
        onSend={vi.fn()}
        onVoice={vi.fn()}
        onClear={vi.fn()}
        lastUserMessage="book tennis tomorrow"
        disabled={false}
      />,
    );

    const input = screen.getByLabelText("Message");
    input.focus();
    await user.keyboard("{ArrowUp}");

    expect(input).toHaveValue("book tennis tomorrow");
  });

  it("does not overwrite existing text on ArrowUp", async () => {
    const user = userEvent.setup();
    render(
      <MessageInput
        onSend={vi.fn()}
        onVoice={vi.fn()}
        onClear={vi.fn()}
        lastUserMessage="book tennis tomorrow"
        disabled={false}
      />,
    );

    const input = screen.getByLabelText("Message");
    await user.type(input, "already typing");
    await user.keyboard("{ArrowUp}");

    expect(input).toHaveValue("already typing");
  });

  it("is a no-op on ArrowUp when there is no last user message", async () => {
    const user = userEvent.setup();
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);

    const input = screen.getByLabelText("Message");
    input.focus();
    await user.keyboard("{ArrowUp}");

    expect(input).toHaveValue("");
  });

  // ── Mic button ───────────────────────────────────────────────────────────

  it("mic button is labeled 'Start voice input' when not recording", () => {
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeInTheDocument();
  });

  it("mic button is labeled 'Stop recording' and shows Listening… while recording", () => {
    mockRecorder({ isRecording: true });
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);
    expect(screen.getByRole("button", { name: "Stop recording" })).toBeInTheDocument();
    expect(screen.getByText("Listening…")).toBeInTheDocument();
  });

  it("mic button is disabled when unsupported", () => {
    mockRecorder({ isSupported: false });
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeDisabled();
  });

  it("mic button is disabled when the input itself is disabled", () => {
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={true} />);
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeDisabled();
  });

  it("text input and Send remain fully functional when voice is unsupported", async () => {
    mockRecorder({ isSupported: false });
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);

    const input = screen.getByLabelText("Message");
    expect(input).toBeEnabled();
    await user.type(input, "book tennis");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("book tennis");
  });

  it("clicking the mic button starts recording and forwards the resulting blob via onVoice", async () => {
    const blob = new Blob(["audio"], { type: "audio/webm" });
    const start = vi.fn().mockResolvedValue(blob);
    mockRecorder({ start });
    const user = userEvent.setup();
    const onVoice = vi.fn();
    render(<MessageInput onSend={vi.fn()} onVoice={onVoice} onClear={vi.fn()} disabled={false} />);

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(start).toHaveBeenCalledOnce();
    expect(onVoice).toHaveBeenCalledWith(blob);
  });

  it("clicking the mic button while recording calls stop(), not start()", async () => {
    const stop = vi.fn();
    const start = vi.fn();
    mockRecorder({ isRecording: true, start, stop });
    const user = userEvent.setup();
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);

    await user.click(screen.getByRole("button", { name: "Stop recording" }));

    expect(stop).toHaveBeenCalledOnce();
    expect(start).not.toHaveBeenCalled();
  });

  it("does not call onVoice when start() resolves null (denied/unsupported)", async () => {
    const start = vi.fn().mockResolvedValue(null);
    mockRecorder({ start });
    const user = userEvent.setup();
    const onVoice = vi.fn();
    render(<MessageInput onSend={vi.fn()} onVoice={onVoice} onClear={vi.fn()} disabled={false} />);

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(onVoice).not.toHaveBeenCalled();
  });

  it("shows the recorder's error message when present and not recording", () => {
    mockRecorder({ error: "Microphone access was denied." });
    render(<MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />);
    expect(screen.getByText("Microphone access was denied.")).toBeInTheDocument();
  });

  it("axe: no violations while idle", async () => {
    const { container } = render(
      <MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("axe: no violations while recording (Listening… state)", async () => {
    mockRecorder({ isRecording: true });
    const { container } = render(
      <MessageInput onSend={vi.fn()} onVoice={vi.fn()} onClear={vi.fn()} disabled={false} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
