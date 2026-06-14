import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../../auth/AuthContext";
import { useUpdateBranding } from "../../hooks/tenantAdminHooks";
import { apiFetch } from "../../lib/api";
import { ApiClientError } from "../../lib/api";
import { type Branding } from "../../lib/branding";
import { messageForCode } from "../../lib/messages";

const field = { display: "block", width: "100%", padding: 8,
  marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)" } as const;

export default function TenantBranding() {
  const { claims } = useAuth();
  const slug = typeof claims?.tenant_slug === "string" ? claims.tenant_slug : undefined;
  const updateBranding = useUpdateBranding();

  const [brandName, setBrandName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#1a4d8f");
  const [secondaryColor, setSecondaryColor] = useState("#0f7b6c");
  const [logoUrl, setLogoUrl] = useState("");

  // Pre-fill form from current branding on mount (slug from JWT claim — ADR-0012 §2).
  const { data: currentBranding } = useQuery({
    queryKey: ["branding", slug],
    queryFn: () => apiFetch<Branding>(`/tenants/${slug}/branding`),
    enabled: !!slug,
  });
  useEffect(() => {
    if (!currentBranding) return;
    setBrandName(currentBranding.brand_name ?? "");
    setPrimaryColor(currentBranding.brand_primary_color ?? "#1a4d8f");
    setSecondaryColor(currentBranding.brand_secondary_color ?? "#0f7b6c");
    setLogoUrl(currentBranding.brand_logo_url ?? "");
  }, [currentBranding]);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(false);
    const body: Record<string, string> = {
      brand_primary_color: primaryColor,
      brand_secondary_color: secondaryColor,
    };
    if (brandName) body.brand_name = brandName;
    if (logoUrl) body.brand_logo_url = logoUrl;
    try {
      await updateBranding.mutateAsync(body);
      setOk(true);
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to save branding.");
    }
  }

  return (
    <main style={{ padding: 24, maxWidth: 480, margin: "0 auto" }}>
      <Link to="/tenant" style={{ color: "var(--color-primary)" }}>← Dashboard</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Branding</h1>
      <form onSubmit={submit}>
        <label>Community name (optional)</label>
        <input style={field} value={brandName}
          onChange={(e) => setBrandName(e.target.value)}
          placeholder="Green Park Residences" />
        <label>Primary color</label>
        <div style={{ display: "flex", gap: 8, marginBottom: "var(--spacing)" }}>
          <input type="color" value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
            style={{ width: 48, height: 36, padding: 2, borderRadius: "var(--radius)",
              border: "1px solid var(--color-text-muted)", cursor: "pointer" }} />
          <input style={{ ...field, marginBottom: 0, flex: 1 }} value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
            placeholder="#1a4d8f" />
        </div>
        <label>Secondary color</label>
        <div style={{ display: "flex", gap: 8, marginBottom: "var(--spacing)" }}>
          <input type="color" value={secondaryColor}
            onChange={(e) => setSecondaryColor(e.target.value)}
            style={{ width: 48, height: 36, padding: 2, borderRadius: "var(--radius)",
              border: "1px solid var(--color-text-muted)", cursor: "pointer" }} />
          <input style={{ ...field, marginBottom: 0, flex: 1 }} value={secondaryColor}
            onChange={(e) => setSecondaryColor(e.target.value)}
            placeholder="#0f7b6c" />
        </div>
        <label>Logo URL (optional)</label>
        <input style={field} value={logoUrl}
          onChange={(e) => setLogoUrl(e.target.value)}
          placeholder="https://example.com/logo.png" />
        <button type="submit" disabled={updateBranding.isPending} style={{ width: "100%",
          padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {updateBranding.isPending ? "Saving…" : "Save branding"}
        </button>
      </form>
      {ok && <p style={{ color: "var(--color-secondary)" }}>Saved ✓</p>}
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
    </main>
  );
}
