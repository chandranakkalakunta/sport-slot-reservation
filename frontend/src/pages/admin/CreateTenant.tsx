import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
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

  return (
    <main className="mx-auto max-w-lg px-4 py-10 space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">New tenant</h1>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="tenant-slug" className="text-sm font-medium text-foreground">
            Slug (subdomain identity)
          </label>
          <Input
            id="tenant-slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
            placeholder="oakwood"
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="tenant-name" className="text-sm font-medium text-foreground">
            Display name
          </label>
          <Input
            id="tenant-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Oakwood Residency"
            required
          />
        </div>
        <Button type="submit" disabled={createTenant.isPending} className="w-full">
          {createTenant.isPending ? "Creating…" : "Create tenant"}
        </Button>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </main>
  );
}
