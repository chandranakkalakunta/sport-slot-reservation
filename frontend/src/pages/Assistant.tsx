import { useEffect, useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { MessageInput } from "../components/assistant/MessageInput";
import { MessageThread } from "../components/assistant/MessageThread";
import { SuggestedPrompts } from "../components/assistant/SuggestedPrompts";
import { ResidentNav } from "../components/ResidentNav";
import {
  type AgentMessage,
  errorMessageFor,
  useAgentConfirm,
  useAgentSendMessage,
  useAgentVoice,
} from "../hooks/agentHooks";
import { base64ToBlob } from "../lib/audio";
import { lastUserAndAgentTurn, loadThread, saveThread } from "../lib/agentSession";
import "../styles/assistant.css";

export default function Assistant() {
  const [thread, setThread] = useState<AgentMessage[]>(() => loadThread());
  const [isTyping, setIsTyping] = useState(false);
  const sendMessage = useAgentSendMessage();
  const confirmAction = useAgentConfirm();
  const voiceMessage = useAgentVoice();

  useEffect(() => {
    saveThread(thread);
  }, [thread]);

  function handleSend(text: string) {
    const recentContext = lastUserAndAgentTurn(thread);
    const userMsg: AgentMessage = { kind: "user", text, timestamp: Date.now() };
    setThread((prev) => [...prev, userMsg]);
    setIsTyping(true);
    sendMessage.mutate({ message: text, recent_context: recentContext ?? undefined }, {
      onSuccess: (reply) => {
        const agentMsg: AgentMessage = {
          kind: "agent",
          text: reply.reply,
          pending_action_id: reply.pending_action_id ?? undefined,
          pending_action_summary: reply.pending_action_summary ?? undefined,
          timestamp: Date.now(),
        };
        setThread((prev) => [...prev, agentMsg]);
        setIsTyping(false);
      },
      onError: (err) => {
        const errMsg: AgentMessage = {
          kind: "agent",
          text: errorMessageFor(err),
          timestamp: Date.now(),
        };
        setThread((prev) => [...prev, errMsg]);
        setIsTyping(false);
      },
    });
  }

  function handleConfirm(pendingActionId: string) {
    setIsTyping(true);
    confirmAction.mutate(pendingActionId, {
      onSuccess: (reply) => {
        setThread((prev) => {
          const updated = prev.map((m) =>
            m.pending_action_id === pendingActionId ? { ...m, dismissed: true } : m,
          );
          const confirmMsg: AgentMessage = {
            kind: "agent",
            text: reply.reply,
            timestamp: Date.now(),
          };
          return [...updated, confirmMsg];
        });
        setIsTyping(false);
      },
      onError: (err) => {
        const errMsg: AgentMessage = {
          kind: "agent",
          text: errorMessageFor(err),
          timestamp: Date.now(),
        };
        setThread((prev) => [...prev, errMsg]);
        setIsTyping(false);
      },
    });
  }

  function handleVoice(audio: Blob) {
    // A spoken turn is a CONFIRM turn iff the latest non-dismissed agent
    // message has a live pending_action_id — mirrors handleConfirm's own
    // pending_action_id keying.
    const latestPending = [...thread].reverse().find((m) => m.kind === "agent" && !m.dismissed);
    const pendingActionId = latestPending?.pending_action_id;

    setIsTyping(true);
    voiceMessage.mutate({ audio, pending_action_id: pendingActionId }, {
      onSuccess: (reply) => {
        const userMsg: AgentMessage = {
          kind: "user",
          text: reply.transcript,
          timestamp: Date.now(),
        };
        const audioUrl = reply.reply_audio
          ? URL.createObjectURL(base64ToBlob(reply.reply_audio, reply.reply_audio_mime ?? "audio/mpeg"))
          : undefined;

        setThread((prev) => {
          const withUser = [...prev, userMsg];

          if (pendingActionId) {
            // CONFIRM TURN — decision drives the UI (ADR-0036/0037).
            if (reply.decision === "affirm" || reply.decision === "deny") {
              const dismissed = withUser.map((m) =>
                m.pending_action_id === pendingActionId ? { ...m, dismissed: true } : m,
              );
              const resultMsg: AgentMessage = {
                kind: "agent",
                text: reply.reply_text,
                audioUrl,
                reply_audio_mime: reply.reply_audio_mime ?? undefined,
                decision: reply.decision,
                timestamp: Date.now() + 1,
              };
              return [...dismissed, resultMsg];
            }
            // ambiguous, or an empty/garbled transcript (decision null) —
            // never guess: re-prompt, keep the pending action alive.
            const repromptMsg: AgentMessage = {
              kind: "agent",
              text: reply.reply_text,
              audioUrl,
              reply_audio_mime: reply.reply_audio_mime ?? undefined,
              decision: reply.decision ?? undefined,
              timestamp: Date.now() + 1,
            };
            return [...withUser, repromptMsg];
          }

          // NORMAL TURN — may itself propose a new pending action.
          const agentMsg: AgentMessage = {
            kind: "agent",
            text: reply.reply_text,
            pending_action_id: reply.pending_action_id ?? undefined,
            pending_action_summary: reply.pending_action_summary ?? undefined,
            audioUrl,
            reply_audio_mime: reply.reply_audio_mime ?? undefined,
            timestamp: Date.now() + 1,
          };
          return [...withUser, agentMsg];
        });
        setIsTyping(false);
      },
      onError: (err) => {
        const errMsg: AgentMessage = {
          kind: "agent",
          text: errorMessageFor(err),
          timestamp: Date.now(),
        };
        setThread((prev) => [...prev, errMsg]);
        setIsTyping(false);
      },
    });
  }

  function handleDismiss(timestamp: number) {
    setThread((prev) =>
      prev.map((m) => (m.timestamp === timestamp ? { ...m, dismissed: true } : m)),
    );
  }

  function handleClear() {
    // Any live pending only ever lived as a field on a thread message —
    // clearing the thread necessarily drops it too, no separate cleanup.
    setThread([]);
  }

  const lastUserMessage = [...thread].reverse().find((m) => m.kind === "user")?.text;
  const inputDisabled = isTyping || sendMessage.isPending || confirmAction.isPending || voiceMessage.isPending;

  return (
    <div style={{ display: "flex", flexDirection: "column", position: "fixed", top: 0, right: 0, bottom: 0, left: 0, paddingBottom: 72 }}>
      <AppHeader>
        <ResidentNav />
      </AppHeader>
      <main style={{
        flex: 1,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        maxWidth: 720,
        width: "100%",
        margin: "0 auto",
        boxSizing: "border-box",
      }}>
        {thread.length === 0 ? (
          <div style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            padding: 24,
          }}>
            <h1 style={{ color: "var(--color-primary)", margin: 0 }}>SlotSense</h1>
            <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginTop: 8 }}>
              Your smart booking assistant — check availability, book, or cancel a slot.
            </p>
            <SuggestedPrompts onSelect={handleSend} />
          </div>
        ) : (
          <MessageThread
            messages={thread}
            isAgentTyping={isTyping}
            onConfirm={handleConfirm}
            onDismiss={handleDismiss}
            isConfirming={confirmAction.isPending}
          />
        )}
        <div style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--color-text-muted)",
        }}>
          <MessageInput
            onSend={handleSend}
            onVoice={handleVoice}
            onClear={handleClear}
            lastUserMessage={lastUserMessage}
            disabled={inputDisabled}
          />
        </div>
      </main>
    </div>
  );
}
