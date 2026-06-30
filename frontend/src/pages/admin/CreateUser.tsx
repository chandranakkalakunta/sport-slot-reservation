import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CredentialDisplay } from "../../components/CredentialDisplay";
import { useCreateUser } from "../../hooks/adminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

export default function CreateUser() {
  const { tenantId } = useParams();
  const [params] = useSearchParams();
  const isFirst = params.get("first") === "1";
  const createUser = useCreateUser(tenantId ?? "");

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [flat, setFlat] = useState("");
  const [role, setRole] = useState(isFirst ? "tenant_admin" : "resident");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ email: string; temp: string } | null>(null);

  function handleRoleChange(e: ChangeEvent<HTMLSelectElement>) {
    setRole(e.target.value);
    setFlat(""); // clear so a stale flat value can't survive a role switch
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await createUser.mutateAsync({
        email, display_name: displayName, role,
        // flat_number is resident-only; omit the key entirely for
        // tenant_admin (the API model accepts it missing or null).
        ...(role === "resident" ? { flat_number: flat } : {}),
      });
      setCreated({ email, temp: res.temp_password });
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to create user.");
    }
  }

  if (created) {
    return (
      <main className="mx-auto max-w-lg px-4 py-10 space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">User created</h1>
        <CredentialDisplay creds={[{ email: created.email, temp_password: created.temp }]} title="User created" />
        <Button
          variant="outline"
          onClick={() => { setCreated(null); setEmail(""); setDisplayName(""); setFlat(""); }}
        >
          Add another
        </Button>
        <p className="text-sm">
          <Link to="/admin" className="text-sm font-medium text-primary hover:underline">← Back to tenants</Link>
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-4 py-10 space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">
        {isFirst ? "Add first admin" : "Add user"}
      </h1>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="cu-email" className="text-sm font-medium text-foreground">
            Email
          </label>
          <Input
            id="cu-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="cu-name" className="text-sm font-medium text-foreground">
            Display name
          </label>
          <Input
            id="cu-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="cu-role" className="text-sm font-medium text-foreground">
            Role
          </label>
          <select
            id="cu-role"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            value={role}
            onChange={handleRoleChange}
          >
            <option value="resident">Resident</option>
            <option value="tenant_admin">Tenant admin</option>
          </select>
        </div>
        {role === "resident" && (
          <div className="space-y-1">
            <label htmlFor="cu-flat" className="text-sm font-medium text-foreground">
              Flat number
            </label>
            <Input
              id="cu-flat"
              value={flat}
              onChange={(e) => setFlat(e.target.value)}
              placeholder="A-101"
              required
            />
          </div>
        )}
        <Button type="submit" disabled={createUser.isPending} className="w-full">
          {createUser.isPending ? "Creating…" : "Create user"}
        </Button>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </main>
  );
}
