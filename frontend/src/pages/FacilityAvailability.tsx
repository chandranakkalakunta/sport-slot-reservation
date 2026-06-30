import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { SlotGrid } from "../components/SlotGrid";
import {
  type Slot, useAvailability, useCreateBooking, useMyBookings,
} from "../hooks/bookingHooks";
import { ApiClientError } from "../lib/api";
import { messageForCode } from "../lib/messages";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function FacilityAvailability() {
  const { facilityId } = useParams();
  const [date, setDate] = useState(todayISO());
  const [picked, setPicked] = useState<Slot | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const { data, isLoading } = useAvailability(facilityId ?? null, date);
  const createBooking = useCreateBooking();
  const { data: myBookings } = useMyBookings();
  const sameDayConfirmed = (myBookings?.items ?? []).filter(
    (b) => b.date === date && b.status === "confirmed",
  ).length;
  // Advisory only; the backend remains authoritative on quota.
  const atQuota = sameDayConfirmed >= 1;

  async function confirm() {
    if (!facilityId || !picked) return;
    setDialogError(null);
    setFeedback(null);
    try {
      const result = await createBooking.mutateAsync({
        facility_id: facilityId, date, start: picked.start,
      });
      setFeedback(result.notice ?? `Booked ${picked.start}–${picked.end}.`);
      setPicked(null);
    } catch (e) {
      const code = e instanceof ApiClientError ? e.code : "UNKNOWN";
      setDialogError(messageForCode(code));
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 space-y-4">
      <Link to="/" className="block text-sm font-medium text-primary underline underline-offset-2 hover:text-primary/70">← Facilities</Link>
      <h1 className="text-2xl font-semibold text-foreground">Availability</h1>

      <div className="flex items-center gap-3">
        <label htmlFor="availability-date" className="text-sm font-medium text-foreground">
          Date
        </label>
        <input
          id="availability-date"
          type="date"
          value={date}
          min={todayISO()}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm tabular-nums text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Slot state legend — state conveyed by TEXT and color, never color alone */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded border border-success bg-success" />
          Available
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded border border-border bg-muted" />
          Unavailable
        </span>
      </div>

      {atQuota && (
        <div className="rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
          You've used today's booking. Cancel one in{" "}
          <Link to="/bookings" className="text-primary underline">
            My bookings
          </Link>{" "}to book another.
        </div>
      )}

      {feedback && <p className="text-sm text-success">{feedback}</p>}
      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && <SlotGrid slots={data.slots} onPick={setPicked} />}

      {picked && (
        <ConfirmDialog
          title="Confirm booking"
          body={
            <>
              <p>{picked.start}–{picked.end} on {date}.</p>
              {picked.reason === "IN_PROGRESS" && (
                <p className="text-sm text-destructive">
                  This slot is already in progress — you'll be booking the
                  remaining time only.
                </p>
              )}
              {dialogError && (
                <p className="text-sm text-destructive">{dialogError}</p>
              )}
            </>
          }
          confirmLabel="Book"
          busy={createBooking.isPending}
          onConfirm={confirm}
          onCancel={() => { setPicked(null); setDialogError(null); }}
        />
      )}
    </main>
  );
}
