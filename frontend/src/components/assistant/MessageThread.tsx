import { useEffect, useRef } from "react";

import type { AgentMessage } from "../../hooks/agentHooks";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

export function MessageThread({
  messages,
  isAgentTyping,
  onConfirm,
  onDismiss,
  isConfirming,
}: {
  messages: AgentMessage[];
  isAgentTyping: boolean;
  onConfirm: (pendingActionId: string) => void;
  onDismiss: (timestamp: number) => void;
  isConfirming: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, isAgentTyping]);

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "16px 16px 0" }}>
      {messages.map((m) => (
        <MessageBubble
          key={m.timestamp}
          message={m}
          onConfirm={onConfirm}
          onDismiss={onDismiss}
          isConfirming={isConfirming}
        />
      ))}
      {isAgentTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
