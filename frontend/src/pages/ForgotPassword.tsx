import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../lib/api";

const NEUTRAL_MSG =
  "If an account exists for that email, a reset link has been sent. Check your inbox.";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await apiFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
    } catch {
      // Enumeration-safe: same confirmation regardless of whether the email exists.
    } finally {
      setBusy(false);
      setDone(true);
    }
  }

  const field = {
    display: "block", width: "100%", padding: 8,
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)",
  } as const;

  if (done) {
    return (
      <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Reset your password</h1>
        <p>{NEUTRAL_MSG}</p>
        <Link to="/signin" style={{ color: "var(--color-primary)" }}>Back to sign in</Link>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>Reset your password</h1>
      <form onSubmit={submit}>
        <input
          style={field}
          type="email"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <button
          type="submit"
          disabled={busy}
          style={{
            width: "100%", padding: 10,
            background: "var(--color-primary)", color: "#fff", border: "none",
            borderRadius: "var(--radius)", cursor: "pointer",
          }}
        >
          {busy ? "Sending…" : "Send reset link"}
        </button>
      </form>
    </main>
  );
}
