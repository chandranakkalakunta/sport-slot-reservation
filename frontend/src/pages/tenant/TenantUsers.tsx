import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { CredentialDisplay, type Credential } from "../../components/CredentialDisplay";
import { Input } from "../../components/ui/input";
import {
  useBulkCreateUsers, useCreateTenantUser, useDeactivateTenantUser,
  useResetTenantUserPassword, useTenantUsers,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

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

  // Deactivate confirm
  const [confirmUid, setConfirmUid] = useState<string | null>(null);

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
      <main className="mx-auto max-w-3xl px-4 py-6 space-y-8">
        <Link to="/tenant" className="text-sm text-primary hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Residents &amp; Admins</h1>

        {/* User list */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground">Active users</h2>
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {active.length === 0 && !isLoading && (
            <p className="text-sm text-muted-foreground">No users yet.</p>
          )}
          <div className="grid gap-2">
            {active.map((u) => (
              <Card key={u.uid}>
                <CardContent className="flex items-center justify-between p-4">
                  <div>
                    <p className="font-semibold text-foreground">{u.display_name}</p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      {u.email} · {u.role}{u.flat_number ? ` · ${u.flat_number}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReset(u.uid, u.email)}
                      disabled={resetPw.isPending}
                    >
                      Issue temp password
                    </Button>
                    {/* De-emphasized trigger per ADR-0028 §5; ConfirmDialog confirms before mutate */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={() => setConfirmUid(u.uid)}
                      disabled={deactivate.isPending}
                    >
                      Deactivate
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          {resetError && <p className="text-sm text-destructive">{resetError}</p>}
          {resetCred && (
            <div className="mt-3">
              <CredentialDisplay creds={[resetCred]} title="Temp password issued" />
            </div>
          )}
        </section>

        {/* Add user form */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Add user</h2>
          {newCred && (
            <div className="mb-4">
              <CredentialDisplay creds={[newCred]} title="User created" />
            </div>
          )}
          <form onSubmit={submitAdd} className="max-w-md space-y-3">
            <div className="space-y-1">
              <label htmlFor="user-email" className="text-sm font-medium text-foreground">
                Email
              </label>
              <Input
                id="user-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="user-name" className="text-sm font-medium text-foreground">
                Display name
              </label>
              <Input
                id="user-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="user-role" className="text-sm font-medium text-foreground">
                Role
              </label>
              <select
                id="user-role"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="resident">Resident</option>
                <option value="tenant_admin">Tenant admin</option>
              </select>
            </div>
            {role === "resident" && (
              <div className="space-y-1">
                <label htmlFor="user-flat" className="text-sm font-medium text-foreground">
                  Flat number
                </label>
                <Input
                  id="user-flat"
                  value={flat}
                  onChange={(e) => setFlat(e.target.value)}
                  placeholder="A-101"
                  required
                />
              </div>
            )}
            <Button type="submit" disabled={createUser.isPending} className="w-full">
              {createUser.isPending ? "Creating…" : "Add user"}
            </Button>
          </form>
          {addError && <p className="text-sm text-destructive">{addError}</p>}
        </section>

        {/* Bulk CSV import */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground">Bulk import (CSV)</h2>
          <p className="text-sm text-muted-foreground">
            CSV headers: email, display_name, flat_number, role, household_id
          </p>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={handleCSV}
            disabled={bulkCreate.isPending}
            className="text-sm text-foreground"
          />
          {bulkCreate.isPending && <p className="text-sm text-muted-foreground">Importing…</p>}
          {bulkError && <p className="text-sm text-destructive">{bulkError}</p>}
          {bulkReport && (
            <div className="space-y-3">
              <p className="text-sm text-foreground tabular-nums">
                Total: {bulkReport.total} · Created: {bulkReport.created} · Failed: {bulkReport.failed}
              </p>
              {bulkCreated.length > 0 && (
                <CredentialDisplay
                  title={`${bulkCreated.length} user(s) created`}
                  creds={bulkCreated
                    .filter((r): r is BulkResult & { temp_password: string } => !!r.temp_password)
                    .map((r) => ({ email: r.email, temp_password: r.temp_password }))}
                />
              )}
              {bulkFailed.length > 0 && (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Failed rows:</p>
                  {bulkFailed.map((r) => (
                    <p key={r.row} className="text-sm text-destructive tabular-nums">
                      Row {r.row} — {r.email}: {r.reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      {confirmUid && (
        <ConfirmDialog
          title="Deactivate user"
          body={<p>Deactivate this user? They won't be able to log in.</p>}
          confirmLabel="Deactivate"
          busy={deactivate.isPending}
          onConfirm={() => { deactivate.mutate(confirmUid); setConfirmUid(null); }}
          onCancel={() => setConfirmUid(null)}
        />
      )}
    </>
  );
}
