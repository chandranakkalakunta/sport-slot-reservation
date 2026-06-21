import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiClientError, apiFetch } from "../lib/api";
import { messageForCode } from "../lib/messages";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  // Capture token into state immediately so it survives the URL strip below.
  const [token] = useState(() => searchParams.get("token") ?? "");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // Strip token from URL so it doesn't persist in browser history or referrer
    // (ADR-0020 security note). Token is already captured in state above.
    if (token) {
      window.history.replaceState(null, "", "/reset");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const field = {
    display: "block", width: "100%", padding: 8,
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)",
  } as const;

  if (!token) {
    return (
      <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Reset your password</h1>
        <p style={{ color: "var(--color-danger)" }}>
          This reset link is invalid or has expired.
        </p>
        <Link to="/forgot-password" style={{ color: "var(--color-primary)" }}>
          Request a new link
        </Link>
      </main>
    );
  }

  if (done) {
    return (
      <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
        <h1 style={{ color: "var(--color-primary)" }}>Reset your password</h1>
        <p>Your password has been reset.</p>
        <Link to="/signin" style={{ color: "var(--color-primary)" }}>Sign in</Link>
      </main>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setTokenError(false);
    if (pw.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }
    if (pw !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await apiFetch("/auth/forgot-password/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: pw }),
      });
      setDone(true);
    } catch (e) {
      if (e instanceof ApiClientError) {
        if (e.code === "RESET_TOKEN_INVALID") setTokenError(true);
        setError(messageForCode(e.code));
      } else {
        setError("Failed to reset password.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>Reset your password</h1>
      <form onSubmit={submit}>
        <input
          style={field}
          type="password"
          placeholder="New password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          required
        />
        <input
          style={field}
          type="password"
          placeholder="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
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
          {busy ? "Resetting…" : "Reset password"}
        </button>
      </form>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
      {tokenError && (
        <Link to="/forgot-password" style={{ color: "var(--color-primary)" }}>
          Request a new link
        </Link>
      )}
    </main>
  );
}
