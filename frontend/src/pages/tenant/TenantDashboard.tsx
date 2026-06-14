import { Link } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";

const card = {
  display: "block", padding: 20, borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)", background: "var(--color-surface)",
  textDecoration: "none", color: "var(--color-text)",
} as const;

export default function TenantDashboard() {
  const { signOut, user } = useAuth();
  return (
    <main style={{ padding: 24, maxWidth: 820, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Tenant Admin</h1>
        <button onClick={() => signOut()} style={{ padding: "6px 12px",
          borderRadius: "var(--radius)", border: "1px solid var(--color-text-muted)",
          background: "transparent", cursor: "pointer" }}>Sign out</button>
      </header>
      <p style={{ color: "var(--color-text-muted)" }}>{user?.email}</p>
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
  );
}
