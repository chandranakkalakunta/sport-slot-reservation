import { describe, expect, it } from "vitest";

import { formatTime12 } from "./timeFormat";

describe("formatTime12", () => {
  it("converts 09:00 to 9:00 AM", () => {
    expect(formatTime12("09:00")).toBe("9:00 AM");
  });

  it("converts 21:00 to 9:00 PM", () => {
    expect(formatTime12("21:00")).toBe("9:00 PM");
  });

  it("converts 00:00 to 12:00 AM", () => {
    expect(formatTime12("00:00")).toBe("12:00 AM");
  });

  it("converts 12:00 to 12:00 PM", () => {
    expect(formatTime12("12:00")).toBe("12:00 PM");
  });

  it("converts 12:30 to 12:30 PM", () => {
    expect(formatTime12("12:30")).toBe("12:30 PM");
  });

  it("converts 00:30 to 12:30 AM", () => {
    expect(formatTime12("00:30")).toBe("12:30 AM");
  });

  it("converts 13:45 to 1:45 PM", () => {
    expect(formatTime12("13:45")).toBe("1:45 PM");
  });

  it("returns input as-is for malformed string", () => {
    expect(formatTime12("not-a-time")).toBe("not-a-time");
  });

  it("returns input as-is for empty string", () => {
    expect(formatTime12("")).toBe("");
  });
});
