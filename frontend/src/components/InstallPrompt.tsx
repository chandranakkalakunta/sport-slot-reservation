import { useState } from "react";
import { X } from "lucide-react";

import { useInstallPrompt } from "../hooks/useInstallPrompt";
import { Button } from "./ui/button";

export function InstallPrompt() {
  const state = useInstallPrompt();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || state.kind === "hidden") return null;

  if (state.kind === "ready") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
        <p className="text-sm text-foreground">Install SlotSense for quick access</p>
        <div className="flex items-center gap-2 shrink-0">
          <Button size="sm" variant="outline" onClick={state.prompt}>
            Install app
          </Button>
          <button
            onClick={() => setDismissed(true)}
            aria-label="Dismiss"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
      <p className="text-sm text-foreground">
        Install: tap <span className="font-medium">Share</span> → <span className="font-medium">Add to Home Screen</span>
      </p>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="text-muted-foreground hover:text-foreground shrink-0"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}
