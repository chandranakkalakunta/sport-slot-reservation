import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { useTenants } from "../../hooks/adminHooks";

export default function TenantList() {
  const { data, isLoading, error } = useTenants();

  return (
    <>
      <AppHeader />
      <main style={{ padding: 24, maxWidth: 820, margin: "0 auto" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Platform Admin</h1>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "16px 0" }}>
        <h2 style={{ margin: 0 }}>Tenants</h2>
        <Link to="/admin/tenants/new" style={{ padding: "8px 16px",
          background: "var(--color-primary)", color: "#fff", borderRadius: "var(--radius)",
          textDecoration: "none" }}>+ New tenant</Link>
      </div>
      {isLoading && <p>Loading tenants…</p>}
      {error && <p style={{ color: "var(--color-danger)" }}>Couldn't load tenants.</p>}
      <div style={{ display: "grid", gap: "var(--spacing)" }}>
        {data?.items.map((t) => (
          <div key={t.tenant_id} style={{ padding: 16, borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)", background: "var(--color-surface)" }}>
            <strong>{t.display_name ?? t.name ?? t.slug}</strong>
            <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
              slug: {t.slug} · {t.active === false ? "inactive" : "active"}
            </div>
            <Link to={`/admin/tenants/${t.tenant_id}/users/new`}
              style={{ color: "var(--color-primary)", fontSize: 13 }}>
              + Add admin/user
            </Link>
          </div>
        ))}
      </div>
      </main>
    </>
  );
}
