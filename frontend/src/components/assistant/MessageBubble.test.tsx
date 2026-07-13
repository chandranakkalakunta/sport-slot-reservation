import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe, toHaveNoViolations } from "jest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AgentMessage } from "../../hooks/agentHooks";
import { MessageBubble } from "./MessageBubble";

expect.extend(toHaveNoViolations);

const noop = vi.fn();

const AGENT_MSG: AgentMessage = {
  kind: "agent",
  text: "Booked Tennis Court 1.",
  timestamp: 1000,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MessageBubble — audio playback", () => {
  it("renders no audio element when the message has no audioUrl", () => {
    render(<MessageBubble message={AGENT_MSG} onConfirm={noop} onDismiss={noop} isConfirming={false} />);
    expect(document.querySelector("audio")).toBeNull();
  });

  it("auto-plays on arrival and shows no fallback button when autoplay succeeds", async () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    render(<MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />);

    await waitFor(() => expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce());
    expect(screen.queryByRole("button", { name: "Play voice reply" })).toBeNull();
  });

  it("shows a fallback play button when autoplay is blocked", async () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValue(new Error("NotAllowedError"));
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    render(<MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />);

    expect(await screen.findByRole("button", { name: "Play voice reply" })).toBeInTheDocument();
  });

  it("fallback play button retries playback on click", async () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play")
      .mockRejectedValueOnce(new Error("NotAllowedError"))
      .mockResolvedValueOnce(undefined);
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };
    const user = userEvent.setup();

    render(<MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />);

    const playButton = await screen.findByRole("button", { name: "Play voice reply" });
    await user.click(playButton);

    await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
  });

  it("renders the <audio> element with the given src", () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    render(<MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />);

    const audioEl = document.querySelector("audio");
    expect(audioEl).toHaveAttribute("src", "blob:fake-url");
  });

  it("axe: no violations with a blocked-autoplay play button visible", async () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValue(new Error("NotAllowedError"));
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    const { container } = render(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />,
    );
    await screen.findByRole("button", { name: "Play voice reply" });

    // preload: false — axe-core otherwise tries to preload the <audio> src
    // to inspect media metadata; jsdom can't load a fake blob: URL, so it
    // burns its own ~10s internal timeout before continuing regardless.
    // Not a real a11y check for this element (no captions rule applies to
    // a synthesized voice reply); disabling preload just skips the stall.
    const result = await axe(container, { preload: false });
    expect(result).toHaveNoViolations();
  });

  it("never renders audio for user-kind messages", () => {
    const userMsgWithAudio: AgentMessage = {
      kind: "user", text: "book tennis", timestamp: 2000,
      audioUrl: "blob:should-not-render",
    };
    render(<MessageBubble message={userMsgWithAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} />);
    expect(document.querySelector("audio")).toBeNull();
  });
});

describe("MessageBubble — VOICE-BARGE-IN (mic input stops reply playback)", () => {
  it("pauses in-progress auto-played audio when isRecording flips true", async () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    const { rerender } = render(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} isRecording={false} />,
    );
    await waitFor(() => expect(play).toHaveBeenCalledOnce());
    expect(pause).not.toHaveBeenCalled();

    rerender(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} isRecording={true} />,
    );

    expect(pause).toHaveBeenCalledOnce();
  });

  it("pauses fallback (manually resumed) playback when isRecording flips true", async () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValue(new Error("NotAllowedError"));
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    const { rerender } = render(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} isRecording={false} />,
    );
    await screen.findByRole("button", { name: "Play voice reply" });

    rerender(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} isRecording={true} />,
    );

    expect(pause).toHaveBeenCalledOnce();
  });

  it("does not pause playback when isRecording stays false", async () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    const withAudio: AgentMessage = { ...AGENT_MSG, audioUrl: "blob:fake-url" };

    render(
      <MessageBubble message={withAudio} onConfirm={noop} onDismiss={noop} isConfirming={false} isRecording={false} />,
    );
    await waitFor(() => expect(play).toHaveBeenCalledOnce());

    expect(pause).not.toHaveBeenCalled();
  });
});
