import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applyMode, getActiveMode, getInitialMode } from "./themeMode";

// Reset DOM + localStorage between tests
beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.mode;
  document.documentElement.style.removeProperty("--color-primary");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getInitialMode", () => {
  it("returns 'light' by default (no storage, light system)", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: false,
    } as MediaQueryList);
    expect(getInitialMode()).toBe("light");
  });

  it("follows system preference when unset in storage", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: true,
    } as MediaQueryList);
    expect(getInitialMode()).toBe("dark");
  });

  it("returns stored 'dark' even if system is light", () => {
    localStorage.setItem("slotsense-theme", "dark");
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: false,
    } as MediaQueryList);
    expect(getInitialMode()).toBe("dark");
  });

  it("returns stored 'light' even if system is dark", () => {
    localStorage.setItem("slotsense-theme", "light");
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: true,
    } as MediaQueryList);
    expect(getInitialMode()).toBe("light");
  });
});

describe("applyMode", () => {
  it("sets data-mode=dark on documentElement for dark", () => {
    applyMode("dark");
    expect(document.documentElement.dataset.mode).toBe("dark");
  });

  it("removes data-mode for light", () => {
    document.documentElement.dataset.mode = "dark";
    applyMode("light");
    expect(document.documentElement.dataset.mode).toBeUndefined();
  });

  it("persists choice to localStorage", () => {
    applyMode("dark");
    expect(localStorage.getItem("slotsense-theme")).toBe("dark");
    applyMode("light");
    expect(localStorage.getItem("slotsense-theme")).toBe("light");
  });

  it("does NOT set or clear --color-primary (branding coexistence)", () => {
    // Pre-set a runtime brand override
    document.documentElement.style.setProperty("--color-primary", "#d6336c");

    applyMode("dark");
    expect(
      document.documentElement.style.getPropertyValue("--color-primary")
    ).toBe("#d6336c");

    applyMode("light");
    expect(
      document.documentElement.style.getPropertyValue("--color-primary")
    ).toBe("#d6336c");
  });
});

describe("getActiveMode", () => {
  it("returns 'dark' when data-mode=dark", () => {
    document.documentElement.dataset.mode = "dark";
    expect(getActiveMode()).toBe("dark");
  });

  it("returns 'light' when data-mode absent", () => {
    delete document.documentElement.dataset.mode;
    expect(getActiveMode()).toBe("light");
  });
});
