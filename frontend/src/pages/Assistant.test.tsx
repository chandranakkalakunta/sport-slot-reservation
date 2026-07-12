import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../components/AppHeader", () => ({
  AppHeader: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("../components/ResidentNav", () => ({ ResidentNav: () => null }));

vi.mock("../hooks/useVoiceRecorder", () => ({ useVoiceRecorder: vi.fn() }));

vi.mock("../hooks/agentHooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../hooks/agentHooks")>();
  return {
    ...actual,
    useAgentSendMessage: vi.fn(),
    useAgentConfirm: vi.fn(),
    useAgentVoice: vi.fn(),
  };
});

vi.mock("../lib/agentSession", () => ({
  loadThread: vi.fn(() => []),
  saveThread: vi.fn(),
  lastUserAndAgentTurn: vi.fn(() => null),
}));

import {
  type AgentMessage,
  useAgentConfirm,
  useAgentSendMessage,
  useAgentVoice,
  type VoiceReply,
} from "../hooks/agentHooks";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import * as agentSession from "../lib/agentSession";
import Assistant from "./Assistant";

function withQC(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const PENDING_SUMMARY = {
  action_type: "book" as const,
  facility_name: "Tennis Court 1",
  sport: "tennis",
  date: "2026-07-15",
  start: "18:00",
  end: "19:00",
  facility_id: "f-court1",
};

function mockVoiceMutate(reply: VoiceReply) {
  const mutate = vi.fn((_vars, opts?: { onSuccess?: (r: VoiceReply) => void }) => {
    opts?.onSuccess?.(reply);
  });
  vi.mocked(useAgentVoice).mockReturnValue({
    mutate, isPending: false,
  } as unknown as ReturnType<typeof useAgentVoice>);
  return mutate;
}

function mockRecorderReturnsBlob(blob: Blob) {
  vi.mocked(useVoiceRecorder).mockReturnValue({
    isSupported: true,
    isRecording: false,
    error: null,
    start: vi.fn().mockResolvedValue(blob),
    stop: vi.fn(),
  });
}

const BLOB = new Blob(["audio"], { type: "audio/webm" });

describe("Assistant — voice turn routing", () => {
  beforeEach(() => {
    vi.mocked(useAgentSendMessage).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useAgentSendMessage>);
    vi.mocked(useAgentConfirm).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useAgentConfirm>);
    mockRecorderReturnsBlob(BLOB);
  });

  it("normal turn (no live pending): sends no pending_action_id and renders transcript + reply", async () => {
    vi.mocked(agentSession.loadThread).mockReturnValue([]);
    const mutate = mockVoiceMutate({
      transcript: "book tennis tomorrow",
      reply_text: "Booked Tennis Court 1.",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: null, pending_action_summary: null, decision: null,
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    await waitFor(() => expect(mutate).toHaveBeenCalled());
    expect(mutate.mock.calls[0][0]).toEqual({ audio: BLOB, pending_action_id: undefined });

    expect(await screen.findByText("book tennis tomorrow")).toBeInTheDocument();
    expect(await screen.findByText("Booked Tennis Court 1.")).toBeInTheDocument();
  });

  it("normal turn that proposes a booking renders the ProposalCard", async () => {
    vi.mocked(agentSession.loadThread).mockReturnValue([]);
    mockVoiceMutate({
      transcript: "book tennis tomorrow at 6pm",
      reply_text: "Confirm booking Tennis Court 1 tomorrow at 18:00?",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: "pa-999", pending_action_summary: PENDING_SUMMARY, decision: null,
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(await screen.findByText("Booking proposal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("confirm turn: a live pending_action_id is sent with the audio", async () => {
    const pendingThread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(pendingThread);
    const mutate = mockVoiceMutate({
      transcript: "yes", reply_text: "Booked!",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: null, pending_action_summary: null, decision: "affirm",
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    await waitFor(() => expect(mutate).toHaveBeenCalled());
    expect(mutate.mock.calls[0][0]).toEqual({ audio: BLOB, pending_action_id: "pa-1" });
  });

  it("confirm AFFIRM: dismisses the pending message and appends the result", async () => {
    const pendingThread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(pendingThread);
    mockVoiceMutate({
      transcript: "yes", reply_text: "Booked!",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: null, pending_action_summary: null, decision: "affirm",
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(await screen.findByText("Booked!")).toBeInTheDocument();
    // The proposal's Confirm button must be gone — the pending message was dismissed.
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("confirm DENY: does not execute, dismisses the pending message, appends cancellation", async () => {
    const pendingThread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(pendingThread);
    mockVoiceMutate({
      transcript: "no", reply_text: "Okay, cancelled.",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: null, pending_action_summary: null, decision: "deny",
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(await screen.findByText("Okay, cancelled.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("confirm AMBIGUOUS: re-prompts and KEEPS the pending action alive", async () => {
    const pendingThread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(pendingThread);
    mockVoiceMutate({
      transcript: "yes no", reply_text: "Please say yes or no to confirm.",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: "pa-1", pending_action_summary: null, decision: "ambiguous",
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(await screen.findByText("Please say yes or no to confirm.")).toBeInTheDocument();
    // The original proposal must STILL be here — never dismissed on ambiguous.
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("confirm turn with an empty/garbled transcript (decision null): re-prompts and keeps pending alive", async () => {
    const pendingThread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(pendingThread);
    mockVoiceMutate({
      transcript: "", reply_text: "Sorry, I didn't catch that.",
      reply_audio: null, reply_audio_mime: null,
      pending_action_id: "pa-1", pending_action_summary: null, decision: null,
    });
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    await user.click(screen.getByRole("button", { name: "Start voice input" }));

    expect(await screen.findByText("Sorry, I didn't catch that.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });
});

describe("Assistant — AGENT-UX-01 (up-arrow recall) and AGENT-UX-02 (/clear)", () => {
  beforeEach(() => {
    vi.mocked(useAgentSendMessage).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useAgentSendMessage>);
    vi.mocked(useAgentConfirm).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useAgentConfirm>);
    vi.mocked(useAgentVoice).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof useAgentVoice>);
    mockRecorderReturnsBlob(BLOB);
  });

  it("ArrowUp on an empty input recalls the most recent user message", async () => {
    const thread: AgentMessage[] = [
      { kind: "user", text: "book tennis tomorrow", timestamp: 100 },
      { kind: "agent", text: "Sure, what time?", timestamp: 200 },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(thread);
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    const input = screen.getByLabelText("Message");
    input.focus();
    await user.keyboard("{ArrowUp}");

    expect(input).toHaveValue("book tennis tomorrow");
  });

  it("/clear empties the thread (ProposalCard and messages disappear) and persists the empty thread", async () => {
    const thread: AgentMessage[] = [
      {
        kind: "agent", text: "Confirm booking Tennis Court 1?",
        pending_action_id: "pa-1", pending_action_summary: PENDING_SUMMARY,
        timestamp: Date.now(),
      },
    ];
    vi.mocked(agentSession.loadThread).mockReturnValue(thread);
    const user = userEvent.setup();
    render(withQC(<Assistant />));

    expect(screen.getByText("Confirm booking Tennis Court 1?")).toBeInTheDocument();

    const input = screen.getByLabelText("Message");
    await user.type(input, "/clear{Enter}");

    expect(screen.queryByText("Confirm booking Tennis Court 1?")).toBeNull();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    await waitFor(() => expect(agentSession.saveThread).toHaveBeenCalledWith([]));
  });
});
