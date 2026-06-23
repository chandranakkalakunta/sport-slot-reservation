import { useEffect, useState } from "react";

import type { AgentSummary } from "../../hooks/agentHooks";

const FIVE_MIN = 5 * 60 * 1000;

export function ProposalCard({
  summary,
  timestamp,
  onConfirm,
  onCancel,
  isConfirming,
}: {
  summary: AgentSummary;
  timestamp: number;
  onConfirm: () => void;
  onCancel: () => void;
  isConfirming: boolean;
}) {
  const [expired, setExpired] = useState<boolean>(() => Date.now() - timestamp >= FIVE_MIN);

  useEffect(() => {
    if (expired) return;
    const remaining = FIVE_MIN - (Date.now() - timestamp);
    if (remaining <= 0) { setExpired(true); return; }
    const id = setTimeout(() => setExpired(true), remaining);
    return () => clearTimeout(id);
  }, [expired, timestamp]);

  const heading = summary.action_type === "book" ? "Booking proposal" : "Cancellation proposal";

  return (
    <div style={{
      marginTop: 8,
      padding: 16,
      borderRadius: "var(--radius)",
      border: "1px solid var(--color-text-muted)",
      background: "var(--color-surface)",
      maxWidth: "80%",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 10, color: "var(--color-primary)" }}>
        {heading}
      </div>
      <div style={{ fontSize: 14, display: "grid", gap: 4, marginBottom: 12 }}>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Facility: </span>
          {summary.facility_name.trim()}
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Sport: </span>
          {summary.sport}
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Date: </span>
          {summary.date}
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Time: </span>
          {summary.start}–{summary.end}
        </div>
      </div>
      {expired ? (
        <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: 13 }}>
          This proposal has expired — please ask again.
        </p>
      ) : (
        <div style={{ display: "flex", gap: "var(--spacing)" }}>
          <button
            onClick={onConfirm}
            disabled={isConfirming}
            className="assistant-btn-confirm"
            style={{
              padding: "12px 24px",
              minHeight: 44,
              borderRadius: "var(--radius)",
              border: "none",
              background: "var(--color-primary)",
              color: "#fff",
              cursor: isConfirming ? "not-allowed" : "pointer",
              opacity: isConfirming ? 0.7 : 1,
              fontWeight: 600,
              fontSize: 14,
            }}
          >
            {isConfirming ? "Confirming…" : "Confirm"}
          </button>
          <button
            onClick={onCancel}
            disabled={isConfirming}
            className="assistant-btn-dismiss"
            style={{
              padding: "12px 24px",
              minHeight: 44,
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-danger)",
              background: "transparent",
              color: "var(--color-danger)",
              cursor: isConfirming ? "not-allowed" : "pointer",
              fontSize: 14,
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
