import { type ReactNode } from "react";

export function ConfirmDialog({
  title, body, confirmLabel = "Confirm", onConfirm, onCancel, busy = false,
}: {
  title: string;
  body: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  return (
    <div role="dialog" aria-modal="true" style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
    }}>
      <div style={{
        background: "var(--color-background)", borderRadius: "var(--radius)",
        padding: 24, maxWidth: 360, width: "100%",
      }}>
        <h2 style={{ marginTop: 0, color: "var(--color-primary)" }}>{title}</h2>
        <div style={{ color: "var(--color-text)", marginBottom: 16 }}>{body}</div>
        <div style={{ display: "flex", gap: "var(--spacing)", justifyContent: "flex-end" }}>
          <button onClick={onCancel} disabled={busy} style={{
            padding: "8px 16px", borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)", background: "transparent",
            cursor: "pointer",
          }}>Cancel</button>
          <button onClick={onConfirm} disabled={busy} style={{
            padding: "8px 16px", borderRadius: "var(--radius)", border: "none",
            background: "var(--color-primary)", color: "#fff", cursor: "pointer",
          }}>{busy ? "…" : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
