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
      setDialogError(messageForCode(code)); // stay open, show error in dialog
    }
  }

  return (
    <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <Link to="/" style={{ color: "var(--color-primary)" }}>← Facilities</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Availability</h1>
      <input type="date" value={date} min={todayISO()}
        onChange={(e) => setDate(e.target.value)}
        style={{ padding: 8, borderRadius: "var(--radius)",
          border: "1px solid var(--color-text-muted)", marginBottom: 16 }} />
      {atQuota && (
        <p style={{
          padding: "8px 12px", borderRadius: "var(--radius)",
          background: "var(--color-surface)", color: "var(--color-text-muted)",
        }}>
          You've used today's booking. Cancel one in{" "}
          <Link to="/bookings" style={{ color: "var(--color-primary)" }}>
            My bookings
          </Link>{" "}to book another.
        </p>
      )}
      {feedback && <p style={{ color: "var(--color-secondary)" }}>{feedback}</p>}
      {isLoading && <p>Loading…</p>}
      {data && <SlotGrid slots={data.slots} onPick={setPicked} />}

      {picked && (
        <ConfirmDialog
          title="Confirm booking"
          body={
            <>
              <p>{picked.start}–{picked.end} on {date}.</p>
              {picked.reason === "IN_PROGRESS" && (
                <p style={{ color: "var(--color-danger)" }}>
                  This slot is already in progress — you'll be booking the
                  remaining time only.
                </p>
              )}
              {dialogError && (
                <p style={{ color: "var(--color-danger)" }}>{dialogError}</p>
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
