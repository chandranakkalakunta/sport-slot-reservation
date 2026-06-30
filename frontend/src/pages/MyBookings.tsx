import { useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { Button } from "../components/ui/button";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ListRow } from "../components/ListRow";
import {
  type Booking, useCancelBooking, useFacilities, useMyBookings,
} from "../hooks/bookingHooks";
import { ApiClientError } from "../lib/api";
import { messageForCode } from "../lib/messages";

function facilityName(id: string, facilities?: { id: string; name: string }[]): string {
  return facilities?.find((f) => f.id === id)?.name ?? id;
}

export default function MyBookings() {
  const { data, isLoading } = useMyBookings();
  const { data: facData } = useFacilities();
  const cancel = useCancelBooking();
  const [target, setTarget] = useState<Booking | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function confirmCancel() {
    if (!target) return;
    setDialogError(null);
    try {
      await cancel.mutateAsync({
        id: target.id, facility_id: target.facility_id, date: target.date,
      });
      setFeedback(`Cancelled your ${target.start} booking on ${target.date}.`);
      setTarget(null);
    } catch (e) {
      const code = e instanceof ApiClientError ? e.code : "UNKNOWN";
      setDialogError(messageForCode(code)); // dialog stays OPEN on error
    }
  }

  // Backend filters to confirmed bookings on/after today (tenant timezone).
  const upcoming = data?.items ?? [];

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-4">
        <Link to="/" className="block text-sm font-medium text-primary underline underline-offset-2 hover:text-primary/70">← Facilities</Link>
        <h1 className="text-2xl font-semibold text-foreground">My bookings</h1>
        {feedback && <p className="text-sm text-success">{feedback}</p>}
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && upcoming.length === 0 && (
          <p className="text-sm text-muted-foreground">No upcoming bookings.</p>
        )}
        <div className="space-y-2">
          {upcoming.map((b) => (
            <ListRow
              key={b.id}
              action={
                b.cancellable ? (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => { setDialogError(null); setTarget(b); }}
                  >
                    Cancel
                  </Button>
                ) : (
                  <span className="text-sm text-muted-foreground">Cancellation closed</span>
                )
              }
            >
              <p className="font-semibold text-foreground truncate">
                {facilityName(b.facility_id, facData?.items)}
              </p>
              <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                {b.date} · {b.start}–{b.end}
              </p>
            </ListRow>
          ))}
        </div>

        {target && (
          <ConfirmDialog
            title="Cancel booking"
            body={
              <>
                <p>Cancel your {target.start} booking on {target.date}?</p>
                {dialogError && (
                  <p className="text-sm text-destructive">{dialogError}</p>
                )}
              </>
            }
            confirmLabel="Cancel booking"
            busy={cancel.isPending}
            onConfirm={confirmCancel}
            onCancel={() => { setTarget(null); setDialogError(null); }}
          />
        )}
      </main>
    </>
  );
}
