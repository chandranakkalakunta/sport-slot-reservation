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

// Voice playback data must not be persisted: a blob: object URL does not
// survive a reload anyway, and there is no reason to bloat sessionStorage
// with it. Text + metadata (reply_audio_mime, decision) are lean enough to
// keep as-is.
function stripAudioUrl(message: AgentMessage): AgentMessage {
  if (message.audioUrl === undefined) return message;
  const clone: AgentMessage = { ...message };
  delete clone.audioUrl;
  return clone;
}

export function saveThread(messages: AgentMessage[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(messages.map(stripAudioUrl)));
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
