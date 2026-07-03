import { useState } from "react";
import { X } from "lucide-react";

import { useInstallPrompt } from "../hooks/useInstallPrompt";
import { Button } from "./ui/button";

const DISMISSED_KEY = "slotsense-install-dismissed";

export function InstallPrompt() {
  const state = useInstallPrompt();
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(DISMISSED_KEY) === "1"
  );
  const [showInstructions, setShowInstructions] = useState(false);

  if (dismissed || state.kind === "hidden") return null;

  function handleDismiss() {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  }

  const dismissBtn = (
    <button
      onClick={handleDismiss}
      aria-label="Dismiss"
      className="text-muted-foreground hover:text-foreground shrink-0"
    >
      <X className="size-4" />
    </button>
  );

  // iOS: show Share instructions immediately — no native install prompt exists
  if (state.kind === "ios-hint") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
        <p className="text-sm text-foreground">
          Tap <span className="font-medium">Share</span>{" "}
          → <span className="font-medium">Add to Home Screen</span>
        </p>
        {dismissBtn}
      </div>
    );
  }

  // After tapping Install on Android/other where no native prompt is available yet
  if (showInstructions) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
        <p className="text-sm text-foreground">
          Tap <span className="font-medium">⋮ menu</span>{" "}
          → <span className="font-medium">Install app</span>
        </p>
        {dismissBtn}
      </div>
    );
  }

  // ready (native prompt available) or manual-hint (prompt not yet fired): show Install button
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
      <p className="text-sm text-foreground">Install SlotSense for quick access</p>
      <div className="flex items-center gap-2 shrink-0">
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            if (state.kind === "ready") state.prompt();
            else setShowInstructions(true);
          }}
        >
          Install app
        </Button>
        {dismissBtn}
      </div>
    </div>
  );
}
