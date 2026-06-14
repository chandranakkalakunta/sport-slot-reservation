import { Link } from "react-router-dom";

export default function TenantUsers() {
  return (
    <main style={{ padding: 24, maxWidth: 820, margin: "0 auto" }}>
      <Link to="/tenant" style={{ color: "var(--color-primary)" }}>← Dashboard</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Residents &amp; Admins</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        User management coming in the next release (Phase 5.5b).
      </p>
    </main>
  );
}
