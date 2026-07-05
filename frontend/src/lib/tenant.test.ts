import { expect, test, vi } from "vitest";

import { tenantSlugFromHost } from "./tenant";

test("extracts slug from tenant subdomain", () => {
  expect(tenantSlugFromHost("demo.slotsense.chandraailabs.com")).toBe("demo");
});

test("returns null for unrelated host when no default configured", () => {
  vi.stubEnv("VITE_DEFAULT_TENANT_SLUG", "");
  expect(tenantSlugFromHost("example.com")).toBeNull();
  vi.unstubAllEnvs();
});

test("uses dev fallback on localhost", () => {
  vi.stubEnv("VITE_DEV_TENANT_SLUG", "demo");
  expect(tenantSlugFromHost("localhost")).toBe("demo");
  vi.unstubAllEnvs();
});

test("uses default-tenant fallback on non-subdomain host", () => {
  vi.stubEnv("VITE_DEFAULT_TENANT_SLUG", "demo");
  expect(tenantSlugFromHost("sport-slot-dev.web.app")).toBe("demo");
  vi.unstubAllEnvs();
});

test("real subdomain wins over default", () => {
  vi.stubEnv("VITE_DEFAULT_TENANT_SLUG", "other");
  expect(tenantSlugFromHost("demo.slotsense.chandraailabs.com")).toBe("demo");
  vi.unstubAllEnvs();
});
