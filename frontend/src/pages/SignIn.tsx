import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

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
            style={{ position: "absolute", right: 8, top: 8, background: "none",
              border: "none", cursor: "pointer", color: "var(--color-text-muted)",
              fontSize: 13 }}>
            {showPw ? "Hide" : "Show"}
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
    </main>
  );
}
