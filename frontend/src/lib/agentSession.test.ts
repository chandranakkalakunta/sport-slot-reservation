import { beforeEach, describe, expect, it } from "vitest";

import type { AgentMessage } from "../hooks/agentHooks";
import { lastUserAndAgentTurn, loadThread, saveThread } from "./agentSession";

const MSG_A: AgentMessage = { kind: "user", text: "Book tennis", timestamp: 1000 };
const MSG_B: AgentMessage = { kind: "agent", text: "Sure!", timestamp: 2000 };

beforeEach(() => { sessionStorage.clear(); });

describe("agentSession", () => {
  it("round-trips through sessionStorage", () => {
    saveThread([MSG_A, MSG_B]);
    expect(loadThread()).toEqual([MSG_A, MSG_B]);
  });

  it("loadThread returns [] on empty storage", () => {
    expect(loadThread()).toEqual([]);
  });

  it("loadThread returns [] on malformed JSON without throwing", () => {
    sessionStorage.setItem("sport-slot:assistant-thread", "not-json{{[");
    expect(loadThread()).toEqual([]);
  });

  it("saveThread swallows errors silently", () => {
    expect(() => saveThread([MSG_A])).not.toThrow();
  });

  it("preserves dismissed flag through round-trip", () => {
    const dismissed: AgentMessage = { ...MSG_B, dismissed: true };
    saveThread([MSG_A, dismissed]);
    const loaded = loadThread();
    expect(loaded[1].dismissed).toBe(true);
  });

  it("strips audioUrl before persisting — never bloats sessionStorage with it", () => {
    const withAudio: AgentMessage = { ...MSG_B, audioUrl: "blob:should-not-persist" };
    saveThread([MSG_A, withAudio]);

    const raw = sessionStorage.getItem("sport-slot:assistant-thread");
    expect(raw).not.toContain("should-not-persist");

    const loaded = loadThread();
    expect(loaded[1].audioUrl).toBeUndefined();
  });

  it("keeps reply_audio_mime and decision metadata through round-trip (only audioUrl is stripped)", () => {
    const withMeta: AgentMessage = {
      ...MSG_B, reply_audio_mime: "audio/mpeg", decision: "affirm",
      audioUrl: "blob:should-not-persist",
    };
    saveThread([MSG_A, withMeta]);

    const loaded = loadThread();
    expect(loaded[1].reply_audio_mime).toBe("audio/mpeg");
    expect(loaded[1].decision).toBe("affirm");
    expect(loaded[1].audioUrl).toBeUndefined();
  });
});

describe("lastUserAndAgentTurn", () => {
  it("returns null on empty thread", () => {
    expect(lastUserAndAgentTurn([])).toBeNull();
  });

  it("returns null when thread has only a user message", () => {
    expect(lastUserAndAgentTurn([MSG_A])).toBeNull();
  });

  it("returns null when thread has only an agent message", () => {
    expect(lastUserAndAgentTurn([MSG_B])).toBeNull();
  });

  it("returns the most recent user+agent pair", () => {
    const thread: AgentMessage[] = [
      { kind: "user", text: "First question", timestamp: 1000 },
      { kind: "agent", text: "First reply", timestamp: 2000 },
      { kind: "user", text: "Second question", timestamp: 3000 },
      { kind: "agent", text: "Second reply", timestamp: 4000 },
    ];
    expect(lastUserAndAgentTurn(thread)).toEqual({
      previous_user_message: "Second question",
      previous_agent_reply: "Second reply",
    });
  });

  it("ignores trailing user message without a following agent reply", () => {
    const thread: AgentMessage[] = [
      { kind: "user", text: "First", timestamp: 1000 },
      { kind: "agent", text: "Reply", timestamp: 2000 },
      { kind: "user", text: "Second (unanswered)", timestamp: 3000 },
    ];
    expect(lastUserAndAgentTurn(thread)).toEqual({
      previous_user_message: "First",
      previous_agent_reply: "Reply",
    });
  });
});
