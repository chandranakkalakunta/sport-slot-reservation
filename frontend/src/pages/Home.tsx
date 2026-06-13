import { useAuth } from "../auth/AuthContext";
import { tenantSlugFromHost } from "../lib/tenant";

export default function Home() {
  const { user, claims, signOut } = useAuth();
  const hostTenant = tenantSlugFromHost();
  const tokenTenant = (claims?.tenant_slug as string | undefined) ?? null;
  const mismatch = tokenTenant && hostTenant && tokenTenant !== hostTenant;

  return (
    <main style={{ padding: "24px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>SportSlot</h1>
      <p>Signed in as <strong>{user?.email}</strong></p>
      <p style={{ color: "var(--color-text-muted)" }}>
        Tenant (token): {tokenTenant ?? "—"} · (host): {hostTenant ?? "—"}
      </p>
      {mismatch && (
        <p style={{ color: "var(--color-danger)" }}>
          Tenant mismatch: token says {tokenTenant}, host says {hostTenant}.
        </p>
      )}
      <button onClick={() => signOut()} style={{ marginTop: "var(--spacing)",
        padding: "8px 16px", borderRadius: "var(--radius)",
        border: "1px solid var(--color-text-muted)", cursor: "pointer" }}>
        Sign out
      </button>
    </main>
  );
}
