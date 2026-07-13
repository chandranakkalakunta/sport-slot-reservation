import { Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useVoiceRecorder } from "../../hooks/useVoiceRecorder";

export function MessageInput({
  onSend,
  onVoice,
  onClear,
  onRecordingChange,
  userMessageHistory,
  disabled,
}: {
  onSend: (text: string) => void;
  onVoice: (blob: Blob) => void;
  onClear: () => void;
  /** VOICE-BARGE-IN: notified whenever recording starts/stops, so the
   * parent can pause any in-progress TTS reply playback the moment the
   * mic opens — the user takes priority over the agent's own voice. */
  onRecordingChange?: (isRecording: boolean) => void;
  /** AGENT-UX-01b: the resident's prior user messages, NEWEST-FIRST
   * (index 0 is the most recent). ArrowUp/ArrowDown walk this list like
   * shell history — see handleKey for the full cursor contract. */
  userMessageHistory?: string[];
  disabled: boolean;
}) {
  const [text, setText] = useState("");
  const { isSupported: micSupported, isRecording, start, stop, error: micError } = useVoiceRecorder();

  // AGENT-UX-01b: history cursor. -1 = not walking history (a fresh draft,
  // which may be empty or something the resident is actively typing). 0..
  // history.length-1 = walking, where 0 is the newest prior message.
  const [historyIndex, setHistoryIndex] = useState(-1);
  // The draft in progress when the walk started, restored on ArrowDown past
  // the newest entry. Entering history mode requires an empty input (see
  // the ArrowUp guard below), so this is always "" today — kept as a ref
  // set generically at walk-start so it stays correct if that guard ever
  // loosens, rather than hardcoding "".
  const draftRef = useRef("");
  const history = userMessageHistory ?? [];

  useEffect(() => {
    onRecordingChange?.(isRecording);
  }, [isRecording, onRecordingChange]);

  function resetHistoryCursor() {
    setHistoryIndex(-1);
    draftRef.current = "";
  }

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (trimmed === "/clear") {
      setText("");
      onClear();
      resetHistoryCursor();
      return;
    }
    onSend(trimmed);
    setText("");
    resetHistoryCursor();
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
      return;
    }

    // AGENT-UX-01b: shell-style multi-level history.
    //
    // Entry gate: ArrowUp only STARTS a walk when the input is empty and
    // we're not already walking (historyIndex === -1) — this is the same
    // "never hijack a fresh typed draft" rule AGENT-UX-01 shipped with.
    // Once a walk is underway (historyIndex >= 0), ArrowUp/ArrowDown keep
    // working no matter what's currently in the box: if the resident
    // edits a recalled message and presses ArrowUp again, that edit is
    // DISCARDED and the walk continues further back — shell (bash)
    // behavior, not "stop at the edited line".
    if (e.key === "ArrowUp") {
      if (historyIndex === -1 && text !== "") return; // fresh typed draft — leave it alone
      if (history.length === 0) return; // nothing to recall
      e.preventDefault();
      if (historyIndex === -1) draftRef.current = text; // save the draft before entering history mode
      const nextIndex = Math.min(historyIndex + 1, history.length - 1);
      setHistoryIndex(nextIndex);
      setText(history[nextIndex]);
      return;
    }

    if (e.key === "ArrowDown") {
      if (historyIndex === -1) return; // not walking history — nothing to do
      e.preventDefault();
      const nextIndex = historyIndex - 1;
      if (nextIndex < 0) {
        setHistoryIndex(-1);
        setText(draftRef.current);
      } else {
        setHistoryIndex(nextIndex);
        setText(history[nextIndex]);
      }
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
