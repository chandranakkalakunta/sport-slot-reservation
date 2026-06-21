import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function SignIn() {
  const { signIn, signInWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await signIn(email, password);
      navigate("/");
    } catch {
      setError("Sign-in failed. Check your credentials.");
    }
  }

  const field = { display: "block", width: "100%", padding: "8px",
    marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
    border: "1px solid var(--color-text-muted)" } as const;

  return (
    <main style={{ maxWidth: 360, margin: "10vh auto", padding: "0 16px" }}>
      <h1 style={{ color: "var(--color-primary)" }}>SportSlot</h1>
      <form onSubmit={handleSubmit}>
        <input style={field} type="email" placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
        <div style={{ position: "relative" }}>
          <input style={field} type={showPw ? "text" : "password"}
            placeholder="Password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          <button type="button" onClick={() => setShowPw((s) => !s)}
            aria-label={showPw ? "Hide password" : "Show password"}
            style={{ position: "absolute", right: 8, top: 6, background: "none",
              border: "none", cursor: "pointer", padding: 4,
              color: "var(--color-text-muted)" }}>
            {showPw ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>
        <button type="submit" style={{ width: "100%", padding: "10px",
          background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          Sign in
        </button>
      </form>
      <button onClick={() => signInWithGoogle().then(() => navigate("/"))}
        style={{ width: "100%", padding: "10px", marginTop: "var(--spacing)",
          background: "var(--color-surface)", border: "1px solid var(--color-text-muted)",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
        Continue with Google
      </button>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
      <p style={{ marginTop: "var(--spacing)", fontSize: 14, textAlign: "center" }}>
        <Link to="/forgot-password" style={{ color: "var(--color-primary)" }}>
          Forgot password?
        </Link>
      </p>
    </main>
  );
}
