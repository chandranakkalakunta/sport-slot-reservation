import { useState } from "react";

export interface Credential { email: string; temp_password: string; }

export function CredentialDisplay({ creds, title = "Credentials created" }: {
  creds: Credential[]; title?: string;
}) {
  const [copied, setCopied] = useState(false);
  const block = creds.map((c) =>
    `Email: ${c.email}\nTemporary password: ${c.temp_password}`,
  ).join("\n\n") + "\n\nSign in and you'll be asked to set a new password.";

  async function copy() {
    try {
      await navigator.clipboard.writeText(block);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable; the text is visible to select */ }
  }

  return (
    <div>
      <p style={{ color: "var(--color-danger)", fontWeight: 600 }}>
        {title} — save now, shown only once.
      </p>
      <pre style={{ background: "var(--color-surface)", padding: 12,
        borderRadius: "var(--radius)", whiteSpace: "pre-wrap" }}>{block}</pre>
      <button onClick={copy} style={{ padding: "8px 16px",
        background: "var(--color-primary)", color: "#fff", border: "none",
        borderRadius: "var(--radius)", cursor: "pointer" }}>
        {copied ? "Copied!" : "Copy credentials"}
      </button>
    </div>
  );
}
