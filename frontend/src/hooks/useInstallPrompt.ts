import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const mq = typeof window.matchMedia === "function"
    ? window.matchMedia("(display-mode: standalone)").matches
    : false;
  return mq || ("standalone" in navigator && (navigator as { standalone?: boolean }).standalone === true);
}

export type InstallState =
  | { kind: "ready"; prompt: () => void }    // Android/Chrome: native OS install dialog available
  | { kind: "ios-hint" }                     // iOS Safari: show Share → Add to Home Screen
  | { kind: "manual-hint" }                  // non-standalone, no native prompt yet (show instructions on request)
  | { kind: "hidden" };                      // already installed (standalone)

export function useInstallPrompt(): InstallState {
  const [deferredEvent, setDeferredEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(isStandalone);

  useEffect(() => {
    if (isStandalone()) return;

    function onBeforeInstall(e: Event) {
      e.preventDefault();
      setDeferredEvent(e as BeforeInstallPromptEvent);
    }
    function onInstalled() {
      setInstalled(true);
      setDeferredEvent(null);
    }

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed) return { kind: "hidden" };

  if (deferredEvent) {
    return {
      kind: "ready",
      prompt: () => {
        deferredEvent.prompt();
        deferredEvent.userChoice.then(() => setDeferredEvent(null));
      },
    };
  }

  if (isIOS()) return { kind: "ios-hint" };

  return { kind: "manual-hint" };
}
