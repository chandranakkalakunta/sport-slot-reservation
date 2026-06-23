import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { MessageInput } from "../components/assistant/MessageInput";
import { MessageThread } from "../components/assistant/MessageThread";
import { SuggestedPrompts } from "../components/assistant/SuggestedPrompts";
import {
  type AgentMessage,
  errorMessageFor,
  useAgentConfirm,
  useAgentSendMessage,
} from "../hooks/agentHooks";
import { lastUserAndAgentTurn, loadThread, saveThread } from "../lib/agentSession";
import "../styles/assistant.css";

export default function Assistant() {
  const [thread, setThread] = useState<AgentMessage[]>(() => loadThread());
  const [isTyping, setIsTyping] = useState(false);
  const sendMessage = useAgentSendMessage();
  const confirmAction = useAgentConfirm();

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

  function handleDismiss(timestamp: number) {
    setThread((prev) =>
      prev.map((m) => (m.timestamp === timestamp ? { ...m, dismissed: true } : m)),
    );
  }

  const inputDisabled = isTyping || sendMessage.isPending || confirmAction.isPending;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <AppHeader>
        <Link to="/" style={{
          padding: "6px 12px", borderRadius: "var(--radius)",
          border: "1px solid var(--color-primary)", color: "var(--color-primary)",
          textDecoration: "none", fontSize: 14,
        }}>Facilities</Link>
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
          <MessageInput onSend={handleSend} disabled={inputDisabled} />
        </div>
      </main>
    </div>
  );
}
