import { beforeEach, describe, expect, it } from "vitest";

import type { AgentMessage } from "../hooks/agentHooks";
import { loadThread, saveThread } from "./agentSession";

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
});
