import { Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { AgentMessage } from "../../hooks/agentHooks";
import { ProposalCard } from "./ProposalCard";

function AudioReply({ url, isRecording }: { url: string; isRecording?: boolean }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const playResult = audio.play();
    if (playResult && typeof playResult.then === "function") {
      playResult.catch(() => setBlocked(true));
    }
  }, [url]);

  // VOICE-BARGE-IN: the user takes priority — stop this reply's playback
  // (auto-played or manually resumed via the fallback button) the moment
  // the mic opens, so mic input and TTS never overlap.
  useEffect(() => {
    if (!isRecording) return;
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    audio.currentTime = 0;
  }, [isRecording]);

  function handlePlayClick() {
    audioRef.current?.play().then(
      () => setBlocked(false),
      () => setBlocked(true),
    );
  }

  return (
    <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
      <audio ref={audioRef} src={url} />
      {blocked && (
        <button
          type="button"
          onClick={handlePlayClick}
          aria-label="Play voice reply"
          className="assistant-play-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 10px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)",
            background: "transparent",
            color: "var(--color-text)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          <Play size={12} aria-hidden="true" />
          Play
        </button>
      )}
    </div>
  );
}

export function MessageBubble({
  message,
  onConfirm,
  onDismiss,
  isConfirming,
  isRecording,
}: {
  message: AgentMessage;
  onConfirm: (pendingActionId: string) => void;
  onDismiss: (timestamp: number) => void;
  isConfirming: boolean;
  /** VOICE-BARGE-IN: when true, stop this bubble's reply audio immediately. */
  isRecording?: boolean;
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
      {!isUser && message.audioUrl && <AudioReply url={message.audioUrl} isRecording={isRecording} />}
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
