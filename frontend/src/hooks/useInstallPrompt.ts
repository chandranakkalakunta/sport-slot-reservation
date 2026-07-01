import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const mq = typeof window.matchMedia === "function"
    ? window.matchMedia("(display-mode: standalone)").matches
    : false;
  return mq || ("standalone" in navigator && (navigator as { standalone?: boolean }).standalone === true);
}

export type InstallState =
  | { kind: "ready"; prompt: () => void }    // Android/Chrome: show install button
  | { kind: "ios-hint" }                     // iOS Safari: show share-menu hint
  | { kind: "hidden" };                      // installed or unsupported

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

  if (isIOS() && !isStandalone()) return { kind: "ios-hint" };

  return { kind: "hidden" };
}
