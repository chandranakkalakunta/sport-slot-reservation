import { expect, test } from "vitest";

import { messageForCode } from "./messages";

test("known code maps to English text", () => {
  expect(messageForCode("BOOKING_QUOTA_EXCEEDED")).toMatch(/daily booking limit/i);
});

test("unknown code falls back to the code itself", () => {
  expect(messageForCode("NONSENSE_CODE")).toBe("NONSENSE_CODE");
});

test("tenant override wins over catalog", () => {
  expect(
    messageForCode("BOOKING_QUOTA_EXCEEDED", "en",
      { BOOKING_QUOTA_EXCEEDED: "Custom society message" }),
  ).toBe("Custom society message");
});
