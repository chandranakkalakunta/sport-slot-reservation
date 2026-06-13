import { expect, test, vi } from "vitest";

import { tenantSlugFromHost } from "./tenant";

test("extracts slug from tenant subdomain", () => {
  expect(tenantSlugFromHost("demo.sportbook.chandraailabs.com")).toBe("demo");
});

test("returns null for unrelated host", () => {
  expect(tenantSlugFromHost("example.com")).toBeNull();
});

test("uses dev fallback on localhost", () => {
  vi.stubEnv("VITE_DEV_TENANT_SLUG", "demo");
  expect(tenantSlugFromHost("localhost")).toBe("demo");
  vi.unstubAllEnvs();
});
