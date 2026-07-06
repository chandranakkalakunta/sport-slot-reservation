/**
 * Phase 13.8 tests: apiFetch behaviour for AUTH_INVALID_TOKEN 401 with
 * "Token missing provisioned claims".
 *
 * Only the claims-specific case triggers the registered handler.
 * Other 401 reasons (AUTH_MISSING_TOKEN, "Token verification failed") must NOT
 * trigger it — those are different failure modes handled differently.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./firebase", () => ({ auth: { currentUser: null } }));

import { apiFetch, ApiClientError, setClaimsErrorHandler } from "./api";

function mockFetch(status: number, body: object) {
  const response = new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

describe("apiFetch — AUTH_INVALID_TOKEN handler", () => {
  let claimsErrorCalled: boolean;

  beforeEach(() => {
    claimsErrorCalled = false;
    setClaimsErrorHandler(() => { claimsErrorCalled = true; });
  });

  it("calls the claims-error handler on 401 AUTH_INVALID_TOKEN with missing-claims message", async () => {
    mockFetch(401, {
      code: "AUTH_INVALID_TOKEN",
      message: "Token missing provisioned claims",
      request_id: "req-1",
    });
    await expect(apiFetch("/test")).rejects.toBeInstanceOf(ApiClientError);
    expect(claimsErrorCalled).toBe(true);
  });

  it("does NOT call handler on 401 AUTH_MISSING_TOKEN (different failure mode)", async () => {
    mockFetch(401, {
      code: "AUTH_MISSING_TOKEN",
      message: "Missing bearer token",
      request_id: "req-2",
    });
    await expect(apiFetch("/test")).rejects.toBeInstanceOf(ApiClientError);
    expect(claimsErrorCalled).toBe(false);
  });

  it("does NOT call handler on 401 AUTH_INVALID_TOKEN with different message (bad token, not stale claims)", async () => {
    mockFetch(401, {
      code: "AUTH_INVALID_TOKEN",
      message: "Token verification failed",
      request_id: "req-3",
    });
    await expect(apiFetch("/test")).rejects.toBeInstanceOf(ApiClientError);
    expect(claimsErrorCalled).toBe(false);
  });

  it("does NOT call handler when no handler is registered (null safe)", async () => {
    setClaimsErrorHandler(null);
    mockFetch(401, {
      code: "AUTH_INVALID_TOKEN",
      message: "Token missing provisioned claims",
    });
    // Should not throw; apiFetch throws ApiClientError but handler is silent
    await expect(apiFetch("/test")).rejects.toBeInstanceOf(ApiClientError);
    expect(claimsErrorCalled).toBe(false);
  });

  it("does NOT call handler on successful 200 response", async () => {
    mockFetch(200, { data: "ok" });
    await expect(apiFetch("/test")).resolves.toEqual({ data: "ok" });
    expect(claimsErrorCalled).toBe(false);
  });
});
