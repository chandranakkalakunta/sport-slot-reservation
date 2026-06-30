const PROMPTS = [
  "Book tennis tomorrow",
  "Is tennis free today?",
  "Is football available tomorrow?",
  "Book badminton this Saturday",
];

export function SuggestedPrompts({ onSelect }: { onSelect: (prompt: string) => void }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--spacing)", marginTop: 16 }}>
      {PROMPTS.map((p) => (
        <button
          key={p}
          onClick={() => onSelect(p)}
          className="assistant-chip"
          style={{
            padding: "12px 16px",
            minHeight: 44,
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)",
            background: "transparent",
            color: "var(--color-text-muted)",
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
