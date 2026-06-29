import { cn } from "../lib/utils";
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
  if (slots.length === 0) {
    return <p className="text-sm text-muted-foreground">No slots available.</p>;
  }

  return (
    <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(96px,1fr))]">
      {slots.map((s) => {
        const displayLabel = s.bookable
          ? "available"
          : s.reason ? (REASON_LABEL[s.reason] ?? s.reason) : null;
        return (
          <button
            key={s.start}
            onClick={() => s.bookable && onPick(s)}
            disabled={!s.bookable}
            className={cn(
              "min-h-[44px] w-full rounded-md border px-2 py-2 text-sm text-center transition-colors",
              s.bookable
                ? "border-success bg-success text-success-foreground hover:opacity-90 cursor-pointer"
                : "border-border bg-muted text-muted-foreground cursor-not-allowed",
            )}
          >
            <div className="font-medium tabular-nums">{s.start}</div>
            {displayLabel && <div className="text-xs mt-0.5">{displayLabel}</div>}
          </button>
        );
      })}
    </div>
  );
}
