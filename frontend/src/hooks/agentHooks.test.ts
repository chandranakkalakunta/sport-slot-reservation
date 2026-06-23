import { describe, expect, it } from "vitest";

import { ApiClientError } from "../lib/api";
import { errorMessageFor } from "./agentHooks";

function makeApiError(code: string, request_id?: string): ApiClientError {
  return new ApiClientError({ code, message: "test", status: 400, request_id });
}

describe("errorMessageFor", () => {
  it("maps a known ApiClientError code to the catalog message", () => {
    const result = errorMessageFor(makeApiError("SLOT_NOT_BOOKABLE"));
    expect(result).toBe("That slot can't be booked.");
  });

  it("appends 8-char request_id ref when present", () => {
    const result = errorMessageFor(makeApiError("SLOT_NOT_BOOKABLE", "abcdef1234567890"));
    expect(result).toBe("That slot can't be booked. (ref: abcdef12)");
  });

  it("does not append ref when request_id is absent", () => {
    const result = errorMessageFor(makeApiError("ALREADY_BOOKED"));
    expect(result).not.toMatch(/ref:/);
    expect(result).toBe("That slot was just taken.");
  });

  it("returns the code itself for an unknown code (catalog fallback)", () => {
    const result = errorMessageFor(makeApiError("SOME_FUTURE_CODE"));
    expect(result).toBe("SOME_FUTURE_CODE");
  });

  it("returns network-error message for a plain Error", () => {
    const result = errorMessageFor(new Error("Network failure"));
    expect(result).toBe(
      "Couldn't reach the assistant. Check your connection and try again.",
    );
  });

  it("returns network-error message for a TypeError", () => {
    const result = errorMessageFor(new TypeError("Failed to fetch"));
    expect(result).toBe(
      "Couldn't reach the assistant. Check your connection and try again.",
    );
  });

  it("returns network-error message for non-Error throws (e.g. null)", () => {
    const result = errorMessageFor(null);
    expect(result).toBe(
      "Couldn't reach the assistant. Check your connection and try again.",
    );
  });
});
