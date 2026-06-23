import type { AgentMessage, RecentContext } from "../hooks/agentHooks";

const KEY = "sport-slot:assistant-thread";

export function loadThread(): AgentMessage[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return [];
    return JSON.parse(raw) as AgentMessage[];
  } catch {
    return [];
  }
}

export function saveThread(messages: AgentMessage[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(messages));
  } catch {
    // storage full or disabled
  }
}

export function lastUserAndAgentTurn(thread: AgentMessage[]): RecentContext | null {
  let lastAgent: AgentMessage | null = null;
  for (let i = thread.length - 1; i >= 0; i--) {
    const m = thread[i];
    if (m.kind === "agent" && lastAgent === null) {
      lastAgent = m;
      continue;
    }
    if (m.kind === "user" && lastAgent !== null) {
      return {
        previous_user_message: m.text,
        previous_agent_reply: lastAgent.text,
      };
    }
  }
  return null;
}
