import { useState } from "react";

import { Button } from "./ui/button";

/**
 * Shown when a claims-related 401 (AUTH_INVALID_TOKEN / "Token missing
 * provisioned claims") is detected — covers the Firebase stale-token window
 * where custom claims haven't propagated to the token yet.
 *
 * Does NOT cover the Content-Length:0 CDN/LB blank-screen case (sub-phase
 * 13.6) — that failure has no HTML/JS loaded at all, so no client-side fix
 * is possible for it.
 */
export function ClaimsErrorFallback({ onRetry }: { onRetry: () => Promise<void> }) {
  const [retrying, setRetrying] = useState(false);

  async function handleRetry() {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-8">
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        Your session couldn't be verified. This can happen right after signing
        in — please retry to continue.
      </p>
      <Button onClick={handleRetry} disabled={retrying}>
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </div>
  );
}
