import { useState } from "react";

export function MessageInput({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div style={{ display: "flex", gap: "var(--spacing)", alignItems: "center" }}>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        placeholder="Ask about availability or bookings…"
        disabled={disabled}
        aria-label="Message"
        style={{
          flex: 1,
          padding: "10px 14px",
          borderRadius: "var(--radius)",
          border: "1px solid var(--color-text-muted)",
          fontSize: 15,
          background: "var(--color-background)",
          color: "var(--color-text)",
          outline: "none",
        }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        className="assistant-send-btn"
        style={{
          padding: "10px 20px",
          minHeight: 44,
          borderRadius: "var(--radius)",
          border: "none",
          background: "var(--color-primary)",
          color: "#fff",
          cursor: disabled || !text.trim() ? "not-allowed" : "pointer",
          fontSize: 15,
          opacity: disabled || !text.trim() ? 0.5 : 1,
        }}
      >
        Send
      </button>
    </div>
  );
}
