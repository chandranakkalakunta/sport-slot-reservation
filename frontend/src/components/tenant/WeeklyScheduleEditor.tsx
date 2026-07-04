import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { DAY_ORDER, type DayName, type TimeRange, type WeeklySchedule } from "../../types/facilitySchedule";

function rangeSummary(ranges: TimeRange[]): string {
  if (ranges.length === 0) return "Closed";
  return ranges.map((r) => `${r.start}–${r.end}`).join(", ");
}

function toMinutes(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function validateRanges(ranges: TimeRange[]): string | null {
  for (let i = 0; i < ranges.length; i++) {
    const { start, end } = ranges[i];
    if (!start || !end) return "All time fields are required.";
    if (toMinutes(start) >= toMinutes(end)) {
      return `Range ${i + 1}: start must be before end.`;
    }
  }
  // Check for overlaps: sort by start, then check consecutive pairs
  const sorted = [...ranges].sort((a, b) => toMinutes(a.start) - toMinutes(b.start));
  for (let i = 0; i < sorted.length - 1; i++) {
    if (toMinutes(sorted[i].end) > toMinutes(sorted[i + 1].start)) {
      return "Ranges must not overlap.";
    }
  }
  return null;
}

interface DayDialogProps {
  day: DayName;
  dayIndex: number;
  value: WeeklySchedule;
  onChange: (next: WeeklySchedule) => void;
}

function DayDialog({ day, dayIndex, value, onChange }: DayDialogProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<TimeRange[]>([]);

  function handleOpen(isOpen: boolean) {
    if (isOpen) {
      const existing = value[day];
      if (existing.length > 0) {
        // Day already has ranges — show its own ranges, never overwritten
        setDraft(existing.map((r) => ({ ...r })));
      } else if (dayIndex > 0) {
        // Carry-forward from previous day (Monday is index 0, exempt)
        const prev = DAY_ORDER[dayIndex - 1];
        setDraft(value[prev].map((r) => ({ ...r })));
      } else {
        // Monday with no ranges — open empty
        setDraft([]);
      }
    }
    setOpen(isOpen);
  }

  function addRange() {
    setDraft((prev) => [...prev, { start: "", end: "" }]);
  }

  function removeRange(idx: number) {
    setDraft((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateRange(idx: number, field: "start" | "end", val: string) {
    setDraft((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [field]: val } : r)),
    );
  }

  function handleSave() {
    onChange({ ...value, [day]: draft });
    setOpen(false);
  }

  const validationError = validateRanges(draft);
  const saveDisabled = validationError !== null;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" aria-label={`Edit ${day} hours`}>
          Edit hours
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="capitalize">{day}</DialogTitle>
        </DialogHeader>

        <div className="space-y-2 py-1">
          {draft.length === 0 && (
            <p className="text-sm text-muted-foreground">No ranges — facility closed this day.</p>
          )}
          {draft.map((range, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <label className="sr-only">Range {idx + 1} start</label>
              <Input
                type="time"
                value={range.start}
                onChange={(e) => updateRange(idx, "start", e.target.value)}
                className="tabular-nums"
                aria-label={`Range ${idx + 1} start`}
              />
              <span className="text-sm text-muted-foreground shrink-0">to</span>
              <label className="sr-only">Range {idx + 1} end</label>
              <Input
                type="time"
                value={range.end}
                onChange={(e) => updateRange(idx, "end", e.target.value)}
                className="tabular-nums"
                aria-label={`Range ${idx + 1} end`}
              />
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0"
                onClick={() => removeRange(idx)}
                aria-label={`Remove range ${idx + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}

          <Button variant="outline" size="sm" onClick={addRange} className="mt-1">
            Add range
          </Button>

          {validationError && (
            <p className="text-sm text-destructive" role="alert">
              {validationError}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handleSave} disabled={saveDisabled}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface WeeklyScheduleEditorProps {
  value: WeeklySchedule;
  onChange: (next: WeeklySchedule) => void;
}

export function WeeklyScheduleEditor({ value, onChange }: WeeklyScheduleEditorProps) {
  return (
    <div className="space-y-2">
      {DAY_ORDER.map((day, idx) => (
        <div key={day} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
          <div className="min-w-0">
            <p className="text-sm font-medium capitalize text-foreground">{day}</p>
            <p className="text-xs text-muted-foreground tabular-nums truncate">
              {rangeSummary(value[day])}
            </p>
          </div>
          <DayDialog day={day} dayIndex={idx} value={value} onChange={onChange} />
        </div>
      ))}
    </div>
  );
}

export function emptyWeeklySchedule(): WeeklySchedule {
  return {
    monday: [], tuesday: [], wednesday: [], thursday: [],
    friday: [], saturday: [], sunday: [],
  };
}
