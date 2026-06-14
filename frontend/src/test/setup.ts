import "@testing-library/jest-dom";

// jsdom doesn't implement navigator.clipboard — provide a configurable stub
// so tests can vi.spyOn(navigator.clipboard, 'writeText').
if (typeof navigator !== "undefined" && !navigator.clipboard) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: () => Promise.resolve() },
    configurable: true,
    writable: true,
  });
}
