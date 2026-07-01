import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../../auth/AuthContext";
import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { useUpdateBranding } from "../../hooks/tenantAdminHooks";
import { apiFetch, ApiClientError } from "../../lib/api";
import { type Branding } from "../../lib/branding";
import { messageForCode } from "../../lib/messages";

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
    <>
      <AppHeader />
      <main className="mx-auto max-w-lg px-4 py-6 space-y-6">
        <Link to="/tenant" className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Branding</h1>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="brand-name" className="text-sm font-medium text-foreground">
              Community name (optional)
            </label>
            <Input
              id="brand-name"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Green Park Residences"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">Primary color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-input p-0.5"
              />
              <Input
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                placeholder="#1a4d8f"
                className="flex-1 tabular-nums"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">Secondary color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={secondaryColor}
                onChange={(e) => setSecondaryColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-input p-0.5"
              />
              <Input
                value={secondaryColor}
                onChange={(e) => setSecondaryColor(e.target.value)}
                placeholder="#0f7b6c"
                className="flex-1 tabular-nums"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="brand-logo" className="text-sm font-medium text-foreground">
              Logo URL (optional)
            </label>
            <Input
              id="brand-logo"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://example.com/logo.png"
            />
          </div>
          <Button type="submit" disabled={updateBranding.isPending} className="w-full">
            {updateBranding.isPending ? "Saving…" : "Save branding"}
          </Button>
        </form>
        {ok && <p className="text-sm text-success">Saved ✓</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </main>
    </>
  );
}
