import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/firebase", () => ({ auth: { currentUser: null } }));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiClientError } from "../lib/api";
import { errorMessageFor, useAgentVoice, type VoiceReply } from "./agentHooks";

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

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return createElement(QueryClientProvider, { client: qc }, children);
}

const VOICE_REPLY: VoiceReply = {
  transcript: "book tennis tomorrow",
  reply_text: "Booked Tennis Court 1.",
  reply_audio: null,
  reply_audio_mime: null,
  pending_action_id: null,
  pending_action_summary: null,
  decision: null,
};

describe("useAgentVoice", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockClear();
  });

  it("posts multipart FormData (never JSON) to /agent/voice", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VOICE_REPLY);
    const { result } = renderHook(() => useAgentVoice(), { wrapper });
    const blob = new Blob(["fake-audio"], { type: "audio/webm" });

    result.current.mutate({ audio: blob });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiFetch).toHaveBeenCalledOnce();
    const [path, init] = vi.mocked(apiFetch).mock.calls[0];
    expect(path).toBe("/agent/voice");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    expect(typeof (init?.body as FormData).get("audio")).not.toBe("string"); // a Blob, not JSON text
  });

  it("includes the audio blob in the FormData under the 'audio' field", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VOICE_REPLY);
    const { result } = renderHook(() => useAgentVoice(), { wrapper });
    const blob = new Blob(["fake-audio"], { type: "audio/webm" });

    result.current.mutate({ audio: blob });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const form = vi.mocked(apiFetch).mock.calls[0][1]?.body as FormData;
    const submitted = form.get("audio");
    expect(submitted).toBeInstanceOf(Blob);
    expect((submitted as Blob).type).toBe("audio/webm");
  });

  it("includes pending_action_id in the FormData when provided (confirm turn)", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VOICE_REPLY);
    const { result } = renderHook(() => useAgentVoice(), { wrapper });
    const blob = new Blob(["fake-audio"], { type: "audio/webm" });

    result.current.mutate({ audio: blob, pending_action_id: "pa-123" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const form = vi.mocked(apiFetch).mock.calls[0][1]?.body as FormData;
    expect(form.get("pending_action_id")).toBe("pa-123");
  });

  it("omits pending_action_id from the FormData when not provided (normal turn)", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VOICE_REPLY);
    const { result } = renderHook(() => useAgentVoice(), { wrapper });
    const blob = new Blob(["fake-audio"], { type: "audio/webm" });

    result.current.mutate({ audio: blob });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const form = vi.mocked(apiFetch).mock.calls[0][1]?.body as FormData;
    expect(form.get("pending_action_id")).toBeNull();
  });

  it("resolves with the VoiceReply from apiFetch", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VOICE_REPLY);
    const { result } = renderHook(() => useAgentVoice(), { wrapper });

    result.current.mutate({ audio: new Blob(["x"]) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(VOICE_REPLY);
  });
});
