import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCreateTenant } from "../../hooks/adminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

export default function CreateTenant() {
  const navigate = useNavigate();
  const createTenant = useCreateTenant();
  const [slug, setSlug] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await createTenant.mutateAsync({ slug, display_name: displayName });
      navigate(`/admin/tenants/${res.tenant_id}/users/new?first=1`);
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to create tenant.");
    }
  }

  const field = { display: "block", width: "100%", padding: 8,
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)" } as const;

  return (
    <main style={{ maxWidth: 480, margin: "6vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>New tenant</h1>
      <form onSubmit={submit}>
        <label>Slug (subdomain identity)</label>
        <input style={field} value={slug}
          onChange={(e) => setSlug(e.target.value.toLowerCase())}
          placeholder="oakwood" required />
        <label>Display name</label>
        <input style={field} value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Oakwood Residency" required />
        <button type="submit" disabled={createTenant.isPending} style={{ width: "100%",
          padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {createTenant.isPending ? "Creating…" : "Create tenant"}
        </button>
      </form>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
    </main>
  );
}
