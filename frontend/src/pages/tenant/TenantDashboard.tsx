import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";

const card = {
  display: "block", padding: 20, borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)", background: "var(--color-surface)",
  textDecoration: "none", color: "var(--color-text)",
} as const;

export default function TenantDashboard() {
  return (
    <>
      <AppHeader />
      <main style={{ padding: 24, maxWidth: 820, margin: "0 auto" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Tenant Admin</h1>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing)", marginTop: 16 }}>
        <Link to="/tenant/facilities" style={card}>
          <strong>Facilities</strong>
          <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            Add and configure courts, timings, slots
          </div>
        </Link>
        <Link to="/tenant/branding" style={card}>
          <strong>Branding</strong>
          <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            Name, colors, logo
          </div>
        </Link>
        <Link to="/tenant/policies" style={card}>
          <strong>Policies</strong>
          <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            Booking window, quota, cancellation
          </div>
        </Link>
        <Link to="/tenant/users" style={card}>
          <strong>Residents &amp; admins</strong>
          <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            Add, import, manage users
          </div>
        </Link>
        </div>
      </main>
    </>
  );
}
