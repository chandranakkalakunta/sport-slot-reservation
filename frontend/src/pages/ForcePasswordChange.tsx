import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiClientError } from "../lib/api";
import { apiFetch } from "../lib/api";
import { messageForCode } from "../lib/messages";

export default function ForcePasswordChange() {
  const navigate = useNavigate();
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (pw !== confirm) { setError("Passwords don't match."); return; }
    setBusy(true);
    try {
      await apiFetch("/users/me/change-password", {
        method: "POST", body: JSON.stringify({ new_password: pw }),
      });
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to change password.");
    } finally {
      setBusy(false);
    }
  }

  const field = { display: "block", width: "100%", padding: 8,
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)" } as const;

  return (
    <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>Set a new password</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        Your account uses a temporary password. Please set a new one to continue.
      </p>
      <form onSubmit={submit}>
        <input style={field} type="password" placeholder="New password"
          value={pw} onChange={(e) => setPw(e.target.value)} required />
        <input style={field} type="password" placeholder="Confirm new password"
          value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        <button type="submit" disabled={busy} style={{ width: "100%", padding: 10,
          background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {busy ? "Saving…" : "Set password"}
        </button>
      </form>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
    </main>
  );
}
