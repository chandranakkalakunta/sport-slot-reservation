import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { useUpdatePolicies } from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

const field = { display: "block", width: "100%", padding: 8,
  marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)" } as const;

export default function TenantPolicies() {
  const updatePolicies = useUpdatePolicies();

  const [horizonDays, setHorizonDays] = useState(14);
  const [openTime, setOpenTime] = useState("06:00");
  const [bufferHours, setBufferHours] = useState(1);
  const [maxSlots, setMaxSlots] = useState(2);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(false);
    try {
      await updatePolicies.mutateAsync({
        booking_horizon_days: horizonDays,
        booking_window_open_time: openTime,
        cancellation_buffer_hours: bufferHours,
        max_slots_per_user_per_sport_per_day: maxSlots,
      });
      setOk(true);
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to save policies.");
    }
  }

  return (
    <main style={{ padding: 24, maxWidth: 480, margin: "0 auto" }}>
      <Link to="/tenant" style={{ color: "var(--color-primary)" }}>← Dashboard</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Booking Policies</h1>
      <form onSubmit={submit}>
        <label>Booking horizon (days)</label>
        <input style={field} type="number" min={1} value={horizonDays}
          onChange={(e) => setHorizonDays(Number(e.target.value))} required />
        <label>Booking window opens at (HH:MM)</label>
        <input style={field} value={openTime}
          onChange={(e) => setOpenTime(e.target.value)}
          placeholder="06:00" required />
        <label>Cancellation buffer (hours before slot)</label>
        <input style={field} type="number" min={0} value={bufferHours}
          onChange={(e) => setBufferHours(Number(e.target.value))} required />
        <label>Max slots per user per sport per day</label>
        <input style={field} type="number" min={1} value={maxSlots}
          onChange={(e) => setMaxSlots(Number(e.target.value))} required />
        <button type="submit" disabled={updatePolicies.isPending} style={{ width: "100%",
          padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {updatePolicies.isPending ? "Saving…" : "Save policies"}
        </button>
      </form>
      {ok && <p style={{ color: "var(--color-secondary)" }}>Saved ✓</p>}
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
    </main>
  );
}
