const STORAGE_KEY = "slotsense-theme";

export type ThemeMode = "light" | "dark";

export function getInitialMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    // localStorage unavailable (SSR / privacy mode)
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function applyMode(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  if (mode === "dark") {
    document.documentElement.dataset.mode = "dark";
  } else {
    delete document.documentElement.dataset.mode;
  }
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // ignore
  }
}

export function getActiveMode(): ThemeMode {
  return document.documentElement.dataset.mode === "dark" ? "dark" : "light";
}
