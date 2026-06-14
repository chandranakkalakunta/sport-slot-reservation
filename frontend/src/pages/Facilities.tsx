import { Link } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { useFacilities } from "../hooks/bookingHooks";

export default function Facilities() {
  const { data, isLoading, error } = useFacilities();

  return (
    <>
      <AppHeader>
        <Link to="/bookings" style={{ padding: "6px 12px", borderRadius: "var(--radius)",
          border: "1px solid var(--color-primary)", color: "var(--color-primary)",
          textDecoration: "none", fontSize: 14 }}>My bookings</Link>
      </AppHeader>
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      {isLoading && <p>Loading facilities…</p>}
      {error && <p style={{ color: "var(--color-danger)" }}>Couldn't load facilities.</p>}
      <div style={{ display: "grid", gap: "var(--spacing)", marginTop: 16 }}>
        {data?.items.filter((f) => f.active).map((f) => (
          <Link key={f.id} to={`/facilities/${f.id}`} style={{
            display: "block", padding: 16, borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)", textDecoration: "none",
            color: "var(--color-text)", background: "var(--color-surface)",
          }}>
            <strong>{f.name}</strong>
            <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
              {f.sport} · {f.open_time}–{f.close_time} · {f.slot_duration_minutes}min
            </div>
          </Link>
        ))}
      </div>
      </main>
    </>
  );
}
