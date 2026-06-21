import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { CredentialDisplay, type Credential } from "../../components/CredentialDisplay";
import {
  useBulkCreateUsers, useCreateTenantUser, useDeactivateTenantUser,
  useResetTenantUserPassword, useTenantUsers,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

const field = { display: "block", width: "100%", padding: 8,
  marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)" } as const;

// Minimal CSV parser — splits on newlines and commas; first row = header.
// Note: quoted fields containing commas are NOT handled (acceptable for v1).
function parseCSV(text: string): Record<string, string>[] {
  const lines = text.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const vals = line.split(",").map((v) => v.trim());
    return Object.fromEntries(headers.map((h, i) => [h, vals[i] ?? ""]));
  });
}

function fieldErrorMsg(e: ApiClientError): string {
  if (e.detail && e.detail.length > 0) {
    return e.detail.map((f) => `${String(f.loc.at(-1))}: ${f.msg}`).join("; ");
  }
  return messageForCode(e.code);
}

export default function TenantUsers() {
  const { data, isLoading } = useTenantUsers();
  const createUser = useCreateTenantUser();
  const deactivate = useDeactivateTenantUser();
  const resetPw = useResetTenantUserPassword();
  const bulkCreate = useBulkCreateUsers();

  // Add-user form
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [flat, setFlat] = useState("");
  const [role, setRole] = useState("resident");
  const [addError, setAddError] = useState<string | null>(null);
  const [newCred, setNewCred] = useState<Credential | null>(null);

  // Reset-password per-user
  const [resetCred, setResetCred] = useState<Credential | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);

  // Bulk CSV
  type BulkResult = { row: number; email: string; status: string; temp_password?: string; reason?: string };
  const [bulkReport, setBulkReport] = useState<{
    total: number; created: number; failed: number; results: BulkResult[];
  } | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);

  async function submitAdd(e: FormEvent) {
    e.preventDefault();
    setAddError(null); setNewCred(null);
    try {
      const res = await createUser.mutateAsync({
        email, display_name: displayName,
        flat_number: role === "resident" ? flat : undefined,
        role,
      });
      setNewCred({ email, temp_password: res.temp_password });
      setEmail(""); setDisplayName(""); setFlat("");
    } catch (err) {
      setAddError(err instanceof ApiClientError ? fieldErrorMsg(err) : "Failed to create user.");
    }
  }

  async function handleReset(uid: string, userEmail: string) {
    setResetCred(null); setResetError(null);
    try {
      const res = await resetPw.mutateAsync(uid);
      setResetCred({ email: userEmail, temp_password: res.temp_password });
    } catch (err) {
      setResetError(err instanceof ApiClientError ? messageForCode(err.code) : "Reset failed.");
    }
  }

  async function handleCSV(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBulkReport(null); setBulkError(null);
    const text = await file.text();
    const rows = parseCSV(text);
    if (rows.length === 0) { setBulkError("No data rows found in CSV."); return; }
    try {
      const report = await bulkCreate.mutateAsync(rows);
      setBulkReport(report);
    } catch (err) {
      setBulkError(err instanceof ApiClientError ? messageForCode(err.code) : "Bulk import failed.");
    }
    e.target.value = "";
  }

  const active = data?.items.filter((u) => u.active !== false) ?? [];
  const bulkCreated = bulkReport?.results.filter((r) => r.status === "created") ?? [];
  const bulkFailed = bulkReport?.results.filter((r) => r.status !== "created") ?? [];

  return (
    <>
      <AppHeader />
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <Link to="/tenant" style={{ color: "var(--color-primary)" }}>← Dashboard</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Residents &amp; Admins</h1>

      {/* User list */}
      <section style={{ marginBottom: 32 }}>
        <h2 style={{ color: "var(--color-primary)" }}>Active users</h2>
        {isLoading && <p>Loading…</p>}
        {active.length === 0 && !isLoading && (
          <p style={{ color: "var(--color-text-muted)" }}>No users yet.</p>
        )}
        {active.map((u) => (
          <div key={u.uid} style={{ display: "flex", justifyContent: "space-between",
            alignItems: "center", padding: "10px 12px", marginBottom: 8,
            borderRadius: "var(--radius)", border: "1px solid var(--color-text-muted)",
            background: "var(--color-surface)" }}>
            <div>
              <strong>{u.display_name}</strong>
              <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
                {u.email} · {u.role}{u.flat_number ? ` · ${u.flat_number}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => handleReset(u.uid, u.email)}
                disabled={resetPw.isPending}
                style={{ padding: "4px 10px", borderRadius: "var(--radius)",
                  border: "1px solid var(--color-primary)", color: "var(--color-primary)",
                  background: "transparent", cursor: "pointer", fontSize: 13 }}>
                Issue temp password
              </button>
              <button onClick={() => deactivate.mutate(u.uid)}
                disabled={deactivate.isPending}
                style={{ padding: "4px 10px", borderRadius: "var(--radius)",
                  border: "1px solid var(--color-danger)", color: "var(--color-danger)",
                  background: "transparent", cursor: "pointer", fontSize: 13 }}>
                Deactivate
              </button>
            </div>
          </div>
        ))}
        {resetError && <p style={{ color: "var(--color-danger)" }}>{resetError}</p>}
        {resetCred && (
          <div style={{ marginTop: 12 }}>
            <CredentialDisplay creds={[resetCred]} title="Temp password issued" />
          </div>
        )}
      </section>

      {/* Add user form */}
      <section style={{ marginBottom: 32 }}>
        <h2 style={{ color: "var(--color-primary)" }}>Add user</h2>
        {newCred && (
          <div style={{ marginBottom: 16 }}>
            <CredentialDisplay creds={[newCred]} title="User created" />
          </div>
        )}
        <form onSubmit={submitAdd}>
          <label>Email</label>
          <input style={field} type="email" value={email}
            onChange={(e) => setEmail(e.target.value)} required />
          <label>Display name</label>
          <input style={field} value={displayName}
            onChange={(e) => setDisplayName(e.target.value)} required />
          <label>Role</label>
          <select style={field} value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="resident">Resident</option>
            <option value="tenant_admin">Tenant admin</option>
          </select>
          {role === "resident" && (
            <>
              <label>Flat number</label>
              <input style={field} value={flat} onChange={(e) => setFlat(e.target.value)}
                placeholder="A-101" required />
            </>
          )}
          <button type="submit" disabled={createUser.isPending} style={{ width: "100%",
            padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
            borderRadius: "var(--radius)", cursor: "pointer" }}>
            {createUser.isPending ? "Creating…" : "Add user"}
          </button>
        </form>
        {addError && <p style={{ color: "var(--color-danger)" }}>{addError}</p>}
      </section>

      {/* Bulk CSV import */}
      <section>
        <h2 style={{ color: "var(--color-primary)" }}>Bulk import (CSV)</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
          CSV headers: email, display_name, flat_number, role, household_id
        </p>
        <input type="file" accept=".csv,text/csv" onChange={handleCSV}
          disabled={bulkCreate.isPending} style={{ marginBottom: "var(--spacing)" }} />
        {bulkCreate.isPending && <p>Importing…</p>}
        {bulkError && <p style={{ color: "var(--color-danger)" }}>{bulkError}</p>}
        {bulkReport && (
          <div style={{ marginTop: 12 }}>
            <p>Total: {bulkReport.total} · Created: {bulkReport.created} · Failed: {bulkReport.failed}</p>
            {bulkCreated.length > 0 && (
              <CredentialDisplay
                title={`${bulkCreated.length} user(s) created`}
                creds={bulkCreated
                  .filter((r): r is BulkResult & { temp_password: string } => !!r.temp_password)
                  .map((r) => ({ email: r.email, temp_password: r.temp_password }))}
              />
            )}
            {bulkFailed.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong>Failed rows:</strong>
                {bulkFailed.map((r) => (
                  <div key={r.row} style={{ color: "var(--color-danger)", fontSize: 13, marginTop: 4 }}>
                    Row {r.row} — {r.email}: {r.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
      </main>
    </>
  );
}
