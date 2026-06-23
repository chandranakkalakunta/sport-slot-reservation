export function TypingIndicator() {
  const dot = (delay: string): React.CSSProperties => ({
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--color-text-muted)",
    display: "inline-block",
    animation: `assistant-pulse 1.4s ease-in-out ${delay} infinite`,
  });
  return (
    <div data-testid="typing-indicator"
      style={{ display: "flex", gap: 4, padding: "10px 14px", alignItems: "center" }}>
      <span style={dot("0s")} />
      <span style={dot("0.2s")} />
      <span style={dot("0.4s")} />
    </div>
  );
}
