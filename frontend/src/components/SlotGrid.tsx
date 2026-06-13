import { type Slot } from "../hooks/bookingHooks";

const REASON_LABEL: Record<string, string> = {
  PAST: "past",
  BOOKED: "booked",
  WINDOW_NOT_OPEN: "opens later",
  BEYOND_HORIZON: "too far ahead",
  IN_PROGRESS: "in progress",
};

export function SlotGrid({
  slots, onPick,
}: {
  slots: Slot[];
  onPick: (slot: Slot) => void;
}) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(96px, 1fr))",
      gap: "var(--spacing)",
    }}>
      {slots.map((s) => {
        const label = s.reason ? REASON_LABEL[s.reason] ?? s.reason : null;
        return (
          <button
            key={s.start}
            onClick={() => s.bookable && onPick(s)}
            disabled={!s.bookable}
            style={{
              padding: "10px 4px", borderRadius: "var(--radius)",
              border: "1px solid var(--color-text-muted)",
              background: s.bookable ? "var(--color-primary)" : "var(--color-surface)",
              color: s.bookable ? "#fff" : "var(--color-text-muted)",
              cursor: s.bookable ? "pointer" : "default",
              fontSize: 13,
            }}
          >
            <div>{s.start}</div>
            {label && <div style={{ fontSize: 10 }}>{label}</div>}
          </button>
        );
      })}
    </div>
  );
}
