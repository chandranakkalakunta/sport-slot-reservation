import { Mic, Square } from "lucide-react";
import { useEffect, useState } from "react";

import { useVoiceRecorder } from "../../hooks/useVoiceRecorder";

export function MessageInput({
  onSend,
  onVoice,
  onClear,
  onRecordingChange,
  lastUserMessage,
  disabled,
}: {
  onSend: (text: string) => void;
  onVoice: (blob: Blob) => void;
  onClear: () => void;
  /** VOICE-BARGE-IN: notified whenever recording starts/stops, so the
   * parent can pause any in-progress TTS reply playback the moment the
   * mic opens — the user takes priority over the agent's own voice. */
  onRecordingChange?: (isRecording: boolean) => void;
  lastUserMessage?: string;
  disabled: boolean;
}) {
  const [text, setText] = useState("");
  const { isSupported: micSupported, isRecording, start, stop, error: micError } = useVoiceRecorder();

  useEffect(() => {
    onRecordingChange?.(isRecording);
  }, [isRecording, onRecordingChange]);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (trimmed === "/clear") {
      setText("");
      onClear();
      return;
    }
    onSend(trimmed);
    setText("");
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
      return;
    }
    // AGENT-UX-01: recall the last message only when the input is empty —
    // never hijack ArrowUp once the resident has started typing/editing.
    if (e.key === "ArrowUp" && text === "" && lastUserMessage) {
      e.preventDefault();
      setText(lastUserMessage);
    }
  }

  async function handleMicClick() {
    if (isRecording) {
      stop();
      return;
    }
    const blob = await start();
    if (blob) onVoice(blob);
  }

  const micDisabled = disabled || !micSupported;

  return (
    <div>
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
          type="button"
          onClick={handleMicClick}
          disabled={micDisabled}
          aria-label={isRecording ? "Stop recording" : "Start voice input"}
          aria-pressed={isRecording}
          className="assistant-mic-btn"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 44,
            height: 44,
            minHeight: 44,
            borderRadius: "var(--radius)",
            border: isRecording ? "1px solid var(--color-danger)" : "1px solid var(--color-text-muted)",
            background: isRecording ? "var(--color-danger)" : "transparent",
            color: isRecording ? "#fff" : "var(--color-text)",
            cursor: micDisabled ? "not-allowed" : "pointer",
            opacity: micDisabled ? 0.5 : 1,
            flexShrink: 0,
          }}
        >
          {isRecording ? <Square size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
        </button>
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
      {isRecording && (
        <p role="status" style={{ fontSize: 12, color: "var(--color-text-muted)", margin: "4px 0 0" }}>
          Listening…
        </p>
      )}
      {micError && !isRecording && (
        <p role="status" style={{ fontSize: 12, color: "var(--color-danger)", margin: "4px 0 0" }}>
          {micError}
        </p>
      )}
    </div>
  );
}
