import { useMutation } from "@tanstack/react-query";

import { ApiClientError, apiFetch } from "../lib/api";
import { messageForCode } from "../lib/messages";

export type ConfirmDecision = "affirm" | "deny" | "ambiguous";

export type AgentMessage = {
  kind: "user" | "agent";
  text: string;
  pending_action_id?: string;
  pending_action_summary?: AgentSummary;
  timestamp: number;
  dismissed?: boolean;
  // Voice-turn playback only — never persisted (agentSession.saveThread
  // strips audioUrl before writing to sessionStorage; a blob: object URL
  // does not survive a reload anyway).
  audioUrl?: string;
  reply_audio_mime?: string;
  decision?: ConfirmDecision;
};

export type AgentSummary = {
  action_type: "book" | "cancel";
  facility_name: string;
  sport: string;
  date: string;
  start: string;
  end: string;
  facility_id?: string;
  booking_id?: string;
};

export type RecentContext = {
  previous_user_message: string;
  previous_agent_reply: string;
};

export interface AgentReply {
  reply: string;
  pending_action_id?: string | null;
  pending_action_summary?: AgentSummary | null;
}

export interface VoiceReply {
  transcript: string;
  reply_text: string;
  reply_audio: string | null;
  reply_audio_mime: string | null;
  pending_action_id: string | null;
  pending_action_summary: AgentSummary | null;
  decision: ConfirmDecision | null;
}

export function errorMessageFor(err: unknown): string {
  if (err instanceof ApiClientError) {
    const text = messageForCode(err.code);
    return err.request_id
      ? `${text} (ref: ${err.request_id.slice(0, 8)})`
      : text;
  }
  return "Couldn't reach the assistant. Check your connection and try again.";
}

export function useAgentSendMessage() {
  return useMutation({
    mutationFn: ({ message, recent_context }: {
      message: string;
      recent_context?: RecentContext;
    }) =>
      apiFetch<AgentReply>("/agent/query", {
        method: "POST",
        body: JSON.stringify({ message, recent_context }),
      }),
  });
}

export function useAgentConfirm() {
  return useMutation({
    mutationFn: (pending_action_id: string) =>
      apiFetch<AgentReply>("/agent/query", {
        method: "POST",
        body: JSON.stringify({ confirm: true, pending_action_id }),
      }),
  });
}

export function useAgentVoice() {
  return useMutation({
    mutationFn: ({ audio, pending_action_id }: {
      audio: Blob;
      pending_action_id?: string;
    }) => {
      const form = new FormData();
      form.append("audio", audio, "voice-input");
      if (pending_action_id) form.append("pending_action_id", pending_action_id);
      // No Content-Type here — apiFetch skips it for FormData bodies so the
      // browser can set the multipart boundary itself.
      return apiFetch<VoiceReply>("/agent/voice", {
        method: "POST",
        body: form,
      });
    },
  });
}
