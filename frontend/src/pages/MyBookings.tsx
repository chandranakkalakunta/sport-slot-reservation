import { useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
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

  const confirmed = data?.items.filter((b) => b.status === "confirmed") ?? [];

  return (
    <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <Link to="/" style={{ color: "var(--color-primary)" }}>← Facilities</Link>
      <h1 style={{ color: "var(--color-primary)" }}>My bookings</h1>
      {feedback && <p style={{ color: "var(--color-secondary)" }}>{feedback}</p>}
      {isLoading && <p>Loading…</p>}
      {!isLoading && confirmed.length === 0 && (
        <p style={{ color: "var(--color-text-muted)" }}>No upcoming bookings.</p>
      )}
      <div style={{ display: "grid", gap: "var(--spacing)", marginTop: 16 }}>
        {confirmed.map((b) => (
          <div key={b.id} style={{
            padding: 16, borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)",
            background: "var(--color-surface)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <div>
              <strong>{facilityName(b.facility_id, facData?.items)}</strong>
              <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
                {b.date} · {b.start}–{b.end}
              </div>
            </div>
            <button onClick={() => { setDialogError(null); setTarget(b); }} style={{
              padding: "6px 12px", borderRadius: "var(--radius)",
              border: "1px solid var(--color-danger)", color: "var(--color-danger)",
              background: "transparent", cursor: "pointer",
            }}>Cancel</button>
          </div>
        ))}
      </div>

      {target && (
        <ConfirmDialog
          title="Cancel booking"
          body={
            <>
              <p>Cancel your {target.start} booking on {target.date}?</p>
              {dialogError && (
                <p style={{ color: "var(--color-danger)" }}>{dialogError}</p>
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
  );
}
