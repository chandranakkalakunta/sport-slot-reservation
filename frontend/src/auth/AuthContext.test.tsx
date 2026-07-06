/**
 * Phase 13.7 tests: slugFromHost helper + onIdTokenChanged mismatch redirect.
 *
 * window.location mocking strategy: vi.stubGlobal replaces the entire
 * `location` object for the test, allowing hostname and href to be set freely
 * in jsdom (which makes window.location read-only by default).
 */
import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { slugFromHost } from "./AuthContext";

// ── slugFromHost unit tests ───────────────────────────────────────────────────

describe("slugFromHost", () => {
  it("returns '' for the exact apex domain", () => {
    expect(slugFromHost("slotsense.chandraailabs.com")).toBe("");
  });

  it("returns the slug for a tenant subdomain", () => {
    expect(slugFromHost("acme.slotsense.chandraailabs.com")).toBe("acme");
    expect(slugFromHost("ddsociety.slotsense.chandraailabs.com")).toBe("ddsociety");
  });

  it("returns null for localhost (dev-safety)", () => {
    expect(slugFromHost("localhost")).toBeNull();
  });

  it("returns null for *.web.app (Firebase hosting preview)", () => {
    expect(slugFromHost("sport-slot-abc123.web.app")).toBeNull();
  });

  it("returns null for *.run.app (Cloud Run preview)", () => {
    expect(slugFromHost("service-abc123.run.app")).toBeNull();
  });

  it("returns null for completely unrecognized hostnames", () => {
    expect(slugFromHost("example.com")).toBeNull();
  });
});

// ── onIdTokenChanged mismatch-redirect tests ──────────────────────────────────
//
// These tests use vi.mock to control Firebase's onIdTokenChanged and
// vi.stubGlobal to control window.location without jsdom's readonly guard.

vi.mock("../lib/firebase", () => ({ auth: {} }));
vi.mock("../lib/branding", () => ({ loadBrandingForSlug: vi.fn() }));

// Capture the onIdTokenChanged callback so tests can trigger it manually.
let _idTokenCallback: ((user: unknown) => Promise<void>) | null = null;

// vi.hoisted ensures mockFbSignOut is available when vi.mock factories run.
const { mockFbSignOut } = vi.hoisted(() => ({
  mockFbSignOut: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("firebase/auth", () => ({
  onIdTokenChanged: (_auth: unknown, cb: (u: unknown) => Promise<void>) => {
    _idTokenCallback = cb;
    return () => {};
  },
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  GoogleAuthProvider: vi.fn(),
  signOut: mockFbSignOut,
}));

import { AuthProvider } from "./AuthContext";
import { loadBrandingForSlug } from "../lib/branding";

function makeUser(claims: Record<string, unknown>) {
  return {
    getIdTokenResult: vi.fn().mockResolvedValue({
      token: "tok",
      claims,
    }),
  };
}

function renderProvider() {
  render(<AuthProvider><div /></AuthProvider>);
}

describe("onIdTokenChanged — mismatch redirect", () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    mockFbSignOut.mockClear();
    vi.mocked(loadBrandingForSlug).mockClear();
    _idTokenCallback = null;
  });

  afterEach(() => {
    vi.stubGlobal("location", originalLocation);
  });

  // ── (a) Apex + tenant_admin → redirect to correct subdomain ──────────────

  it("(a) apex host with tenant_admin claims: signs out and redirects to correct subdomain", async () => {
    const mockLocation = { hostname: "slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "tenant_admin",
        tenant_slug: "ddsociety",
        tenant_id: "t-1",
      }));
    });

    expect(mockFbSignOut).toHaveBeenCalledOnce();
    expect(mockLocation.href).toBe(
      "https://ddsociety.slotsense.chandraailabs.com/signin?redirected=1",
    );
    // loadBrandingForSlug must NOT have been called (redirect happened first)
    expect(loadBrandingForSlug).not.toHaveBeenCalled();
  });

  // ── (a) Apex + resident claims → redirect ────────────────────────────────

  it("(a) apex host with resident claims: signs out and redirects", async () => {
    const mockLocation = { hostname: "slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "resident",
        tenant_slug: "acme",
        tenant_id: "t-2",
      }));
    });

    expect(mockFbSignOut).toHaveBeenCalledOnce();
    expect(mockLocation.href).toBe(
      "https://acme.slotsense.chandraailabs.com/signin?redirected=1",
    );
  });

  // ── (b) Matching subdomain → no redirect ─────────────────────────────────

  it("(b) matching subdomain: no sign-out, no redirect, branding loads normally", async () => {
    const mockLocation = { hostname: "acme.slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "tenant_admin",
        tenant_slug: "acme",
        tenant_id: "t-2",
      }));
    });

    expect(mockFbSignOut).not.toHaveBeenCalled();
    expect(mockLocation.href).toBe("");
    expect(loadBrandingForSlug).toHaveBeenCalledWith("acme");
  });

  // ── (c) Wrong subdomain → redirect ───────────────────────────────────────

  it("(c) wrong subdomain (rvrg host, ddsociety token): signs out and redirects", async () => {
    const mockLocation = { hostname: "rvrg.slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "tenant_admin",
        tenant_slug: "ddsociety",
        tenant_id: "t-3",
      }));
    });

    expect(mockFbSignOut).toHaveBeenCalledOnce();
    expect(mockLocation.href).toBe(
      "https://ddsociety.slotsense.chandraailabs.com/signin?redirected=1",
    );
  });

  // ── (d) platform_admin on apex → no redirect ─────────────────────────────

  it("(d) platform_admin on apex: no sign-out, no redirect (explicitly verified)", async () => {
    const mockLocation = { hostname: "slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "platform_admin",
        // platform_admin has no tenant_slug
      }));
    });

    expect(mockFbSignOut).not.toHaveBeenCalled();
    expect(mockLocation.href).toBe("");
  });

  // ── (e) localhost → no redirect (dev-safety guard) ───────────────────────

  it("(e) localhost host: no redirect regardless of claims (dev-safety guard)", async () => {
    const mockLocation = { hostname: "localhost", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "tenant_admin",
        tenant_slug: "ddsociety",
        tenant_id: "t-4",
      }));
    });

    expect(mockFbSignOut).not.toHaveBeenCalled();
    expect(mockLocation.href).toBe("");
    expect(loadBrandingForSlug).toHaveBeenCalledWith("ddsociety");
  });

  // ── (e) *.web.app → no redirect (dev-safety guard) ───────────────────────

  it("(e) *.web.app host: no redirect regardless of claims", async () => {
    const mockLocation = { hostname: "sport-slot-abc123.web.app", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(makeUser({
        role: "resident",
        tenant_slug: "acme",
        tenant_id: "t-5",
      }));
    });

    expect(mockFbSignOut).not.toHaveBeenCalled();
    expect(mockLocation.href).toBe("");
  });

  // ── unauthenticated (null user) → no redirect ────────────────────────────

  it("null user (signed-out state): no redirect, no error", async () => {
    const mockLocation = { hostname: "slotsense.chandraailabs.com", href: "" };
    vi.stubGlobal("location", mockLocation);

    renderProvider();
    await waitFor(() => expect(_idTokenCallback).not.toBeNull());

    await act(async () => {
      await _idTokenCallback!(null);
    });

    expect(mockFbSignOut).not.toHaveBeenCalled();
    expect(mockLocation.href).toBe("");
  });
});
