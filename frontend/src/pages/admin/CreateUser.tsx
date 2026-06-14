import { type FormEvent, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

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

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await createUser.mutateAsync({
        email, display_name: displayName, flat_number: flat, role,
      });
      setCreated({ email, temp: res.temp_password });
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to create user.");
    }
  }

  const field = { display: "block", width: "100%", padding: 8,
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)" } as const;

  if (created) {
    return (
      <main style={{ maxWidth: 480, margin: "6vh auto", padding: "0 16px" }}>
        <h1 style={{ color: "var(--color-primary)" }}>User created</h1>
        <CredentialDisplay creds={[{ email: created.email, temp_password: created.temp }]} title="User created" />
        <button onClick={() => { setCreated(null); setEmail(""); setDisplayName(""); setFlat(""); }}
          style={{ marginTop: 12, padding: "8px 16px", borderRadius: "var(--radius)",
          border: "1px solid var(--color-text-muted)", background: "transparent", cursor: "pointer" }}>
          Add another
        </button>
        <p style={{ marginTop: 16 }}>
          <Link to="/admin" style={{ color: "var(--color-primary)" }}>← Back to tenants</Link>
        </p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 480, margin: "6vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>
        {isFirst ? "Add first admin" : "Add user"}
      </h1>
      <form onSubmit={submit}>
        <label>Email</label>
        <input style={field} type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
        <label>Display name</label>
        <input style={field} value={displayName}
          onChange={(e) => setDisplayName(e.target.value)} required />
        <label>Flat number</label>
        <input style={field} value={flat}
          onChange={(e) => setFlat(e.target.value)} placeholder="A-101" required />
        <label>Role</label>
        <select style={field} value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="resident">Resident</option>
          <option value="tenant_admin">Tenant admin</option>
        </select>
        <button type="submit" disabled={createUser.isPending} style={{ width: "100%",
          padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {createUser.isPending ? "Creating…" : "Create user"}
        </button>
      </form>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
    </main>
  );
}
