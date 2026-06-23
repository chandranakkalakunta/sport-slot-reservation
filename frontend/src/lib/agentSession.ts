import type { AgentMessage } from "../hooks/agentHooks";

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
