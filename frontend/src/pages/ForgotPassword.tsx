import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AuthCard } from "../components/AuthCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
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

  if (done) {
    return (
      <AuthCard title="Reset your password">
        <p className="text-sm text-foreground">{NEUTRAL_MSG}</p>
        <Link to="/signin" className="text-sm font-medium text-primary hover:underline">
          Back to sign in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Reset your password">
      <form onSubmit={submit} className="space-y-2">
        <div className="space-y-1">
          <label htmlFor="forgot-email" className="text-sm font-medium text-foreground">
            Email address
          </label>
          <Input
            id="forgot-email"
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Sending…" : "Send reset link"}
        </Button>
      </form>
    </AuthCard>
  );
}
