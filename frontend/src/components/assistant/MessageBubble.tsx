import type { AgentMessage } from "../../hooks/agentHooks";
import { ProposalCard } from "./ProposalCard";

export function MessageBubble({
  message,
  onConfirm,
  onDismiss,
  isConfirming,
}: {
  message: AgentMessage;
  onConfirm: (pendingActionId: string) => void;
  onDismiss: (timestamp: number) => void;
  isConfirming: boolean;
}) {
  const isUser = message.kind === "user";
  return (
    <div data-kind={message.kind} style={{
      display: "flex",
      flexDirection: "column",
      alignItems: isUser ? "flex-end" : "flex-start",
      marginBottom: 8,
    }}>
      <div style={{
        maxWidth: "80%",
        padding: "10px 14px",
        borderRadius: "var(--radius)",
        background: isUser ? "var(--color-primary)" : "var(--color-surface)",
        color: isUser ? "#fff" : "var(--color-text)",
        fontSize: 15,
        lineHeight: 1.5,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}>
        {message.text}
      </div>
      {!isUser && message.pending_action_summary && message.pending_action_id && !message.dismissed && (
        <ProposalCard
          summary={message.pending_action_summary}
          timestamp={message.timestamp}
          onConfirm={() => onConfirm(message.pending_action_id!)}
          onCancel={() => onDismiss(message.timestamp)}
          isConfirming={isConfirming}
        />
      )}
    </div>
  );
}
