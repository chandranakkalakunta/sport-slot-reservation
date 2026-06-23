import { useMutation } from "@tanstack/react-query";

import { ApiClientError, apiFetch } from "../lib/api";
import { messageForCode } from "../lib/messages";

export type AgentMessage = {
  kind: "user" | "agent";
  text: string;
  pending_action_id?: string;
  pending_action_summary?: AgentSummary;
  timestamp: number;
  dismissed?: boolean;
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

export interface AgentReply {
  reply: string;
  pending_action_id?: string | null;
  pending_action_summary?: AgentSummary | null;
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
    mutationFn: (message: string) =>
      apiFetch<AgentReply>("/agent/query", {
        method: "POST",
        body: JSON.stringify({ message }),
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
