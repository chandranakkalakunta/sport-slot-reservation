import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getLastBranding } from "../lib/branding";

export function AppHeader({ children }: { children?: React.ReactNode }) {
  const { user, claims, signOut } = useAuth();
  const branding = getLastBranding();
  const role = claims?.role ?? "";
  const roleLabel = role === "platform_admin" ? "Platform admin"
    : role === "tenant_admin" ? "Tenant admin"
    : role === "resident" ? "Resident" : role;

  return (
    <header style={{ display: "flex", justifyContent: "space-between",
      alignItems: "center", padding: "12px 24px", borderBottom: "1px solid var(--color-text-muted)",
      gap: "var(--spacing)", flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {branding?.brand_logo_url && (
          <img src={branding.brand_logo_url} alt="" style={{ height: 32 }} />
        )}
        <Link to="/" style={{ fontWeight: 700, fontSize: 20,
          color: "var(--color-primary)", textDecoration: "none" }}>
          {branding?.brand_name || "SportSlot"}
        </Link>
        {children}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {user && (
          <span style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            {user.email}{roleLabel ? ` · ${roleLabel}` : ""}
          </span>
        )}
        <Link to="/account" style={{ padding: "6px 12px",
          borderRadius: "var(--radius)", border: "1px solid var(--color-text-muted)",
          color: "inherit", textDecoration: "none", fontSize: "inherit" }}>Account</Link>
        <button onClick={() => signOut()} style={{ padding: "6px 12px",
          borderRadius: "var(--radius)", border: "1px solid var(--color-text-muted)",
          background: "transparent", cursor: "pointer" }}>Sign out</button>
      </div>
    </header>
  );
}
