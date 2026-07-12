import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useVoiceRecorder } from "./useVoiceRecorder";

class FakeMediaRecorder {
  static isTypeSupported = vi.fn((type: string) => type === "audio/webm;codecs=opus");

  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(_stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? "audio/webm";
  }

  start() {
    this.state = "recording";
  }

  stop() {
    if (this.state === "inactive") return;
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["chunk"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

function installMediaApis(getUserMedia = vi.fn().mockResolvedValue(_fakeStream())) {
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  return getUserMedia;
}

function _fakeStream(): MediaStream {
  return { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
}

function uninstallMediaApis() {
  vi.unstubAllGlobals();
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
}

describe("useVoiceRecorder", () => {
  afterEach(() => {
    uninstallMediaApis();
    vi.useRealTimers();
  });

  describe("feature detection", () => {
    it("isSupported is false when MediaRecorder is absent", () => {
      Object.defineProperty(navigator, "mediaDevices", {
        value: { getUserMedia: vi.fn() },
        configurable: true,
      });
      const { result } = renderHook(() => useVoiceRecorder());
      expect(result.current.isSupported).toBe(false);
    });

    it("isSupported is false when mediaDevices.getUserMedia is absent", () => {
      Object.defineProperty(navigator, "mediaDevices", { value: {}, configurable: true });
      vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
      const { result } = renderHook(() => useVoiceRecorder());
      expect(result.current.isSupported).toBe(false);
    });

    it("isSupported is true when both APIs are present", () => {
      installMediaApis();
      const { result } = renderHook(() => useVoiceRecorder());
      expect(result.current.isSupported).toBe(true);
    });
  });

  describe("recording lifecycle", () => {
    beforeEach(() => {
      installMediaApis();
    });

    it("start() resolves with a Blob once stop() is called", async () => {
      const { result } = renderHook(() => useVoiceRecorder());

      let blobPromise!: Promise<Blob | null>;
      act(() => {
        blobPromise = result.current.start();
      });
      await waitFor(() => expect(result.current.isRecording).toBe(true));

      act(() => {
        result.current.stop();
      });

      const blob = await blobPromise;
      expect(blob).toBeInstanceOf(Blob);
      await waitFor(() => expect(result.current.isRecording).toBe(false));
    });

    it("never throws uncaught when getUserMedia rejects", async () => {
      const getUserMedia = vi.fn().mockRejectedValue(new Error("boom"));
      installMediaApis(getUserMedia);
      const { result } = renderHook(() => useVoiceRecorder());

      let blob: Blob | null = new Blob(); // sentinel, overwritten below
      await act(async () => {
        blob = await result.current.start();
      });

      expect(blob).toBeNull();
      expect(result.current.isRecording).toBe(false);
    });

    it("sets a friendly error message when permission is denied", async () => {
      const denied = new DOMException("denied", "NotAllowedError");
      installMediaApis(vi.fn().mockRejectedValue(denied));
      const { result } = renderHook(() => useVoiceRecorder());

      await act(async () => {
        await result.current.start();
      });

      expect(result.current.error).toMatch(/denied/i);
    });

    it("sets a generic error message for non-permission getUserMedia failures", async () => {
      installMediaApis(vi.fn().mockRejectedValue(new Error("device busy")));
      const { result } = renderHook(() => useVoiceRecorder());

      await act(async () => {
        await result.current.start();
      });

      expect(result.current.error).toMatch(/couldn't access the microphone/i);
    });

    it("calling start() while already recording is a no-op", async () => {
      const getUserMedia = installMediaApis();
      const { result } = renderHook(() => useVoiceRecorder());

      act(() => {
        void result.current.start();
      });
      await waitFor(() => expect(result.current.isRecording).toBe(true));

      let secondResult: Blob | null = new Blob();
      await act(async () => {
        secondResult = await result.current.start();
      });

      expect(secondResult).toBeNull();
      expect(getUserMedia).toHaveBeenCalledOnce();
    });

    it("auto-stops after the 30s ceiling and resolves a Blob", async () => {
      vi.useFakeTimers();
      const { result } = renderHook(() => useVoiceRecorder());

      let blobPromise!: Promise<Blob | null>;
      act(() => {
        blobPromise = result.current.start();
      });
      // Let the getUserMedia promise microtask resolve under fake timers.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(result.current.isRecording).toBe(true);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });

      const blob = await blobPromise;
      expect(blob).toBeInstanceOf(Blob);
      expect(result.current.isRecording).toBe(false);
    });
  });
});
