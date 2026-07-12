import { useCallback, useEffect, useRef, useState } from "react";

// Hard ceiling — always wins regardless of whether silence detection works.
const MAX_DURATION_MS = 30_000;
// Best-effort silence auto-stop. Deliberately conservative: tap-to-stop and
// the 30s ceiling are the GUARANTEED controls; this is a convenience only.
const SILENCE_RMS_THRESHOLD = 0.02;
const SILENCE_HOLD_MS = 1500;

// Preferred first, most broadly supported second (Safari has no Opus/WebM
// MediaRecorder support but does support audio/mp4). Feature-detected at
// call time via MediaRecorder.isTypeSupported — never assumed.
const CANDIDATE_MIME_TYPES = ["audio/webm;codecs=opus", "audio/mp4"];

function detectSupportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return undefined;
  }
  for (const type of CANDIDATE_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return undefined; // let MediaRecorder pick its own default
}

function isPermissionDenied(err: unknown): boolean {
  return err instanceof DOMException && err.name === "NotAllowedError";
}

export interface UseVoiceRecorderResult {
  isSupported: boolean;
  isRecording: boolean;
  error: string | null;
  /** Starts recording; resolves with the recorded Blob once stopped (by
   * caller, the 30s ceiling, or silence detection). Resolves `null` — never
   * rejects — if the browser is unsupported or the user denies permission;
   * check `error` for why. */
  start: () => Promise<Blob | null>;
  stop: () => void;
}

export function useVoiceRecorder(): UseVoiceRecorderResult {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const ceilingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);

  const isSupported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  const teardown = useCallback(() => {
    if (ceilingTimerRef.current !== null) {
      clearTimeout(ceilingTimerRef.current);
      ceilingTimerRef.current = null;
    }
    if (silenceTimerRef.current !== null) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
    }
    audioContextRef.current = null;
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }, []);

  // Best-effort silence detection — never lets a failure here block
  // recording; wrapped so an unsupported/throwing AudioContext just no-ops.
  const armSilenceDetection = useCallback((stream: MediaStream) => {
    try {
      const AudioCtx: typeof AudioContext | undefined =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;

      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        if (!recorderRef.current || recorderRef.current.state === "inactive") return;
        analyser.getByteTimeDomainData(data);
        let sumSquares = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / data.length);

        if (rms < SILENCE_RMS_THRESHOLD) {
          if (silenceTimerRef.current === null) {
            silenceTimerRef.current = setTimeout(stop, SILENCE_HOLD_MS);
          }
        } else if (silenceTimerRef.current !== null) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      // Silence detection is a convenience only — never block recording on it.
    }
  }, [stop]);

  const start = useCallback((): Promise<Blob | null> => {
    if (!isSupported) {
      setError("Voice input isn't supported in this browser.");
      return Promise.resolve(null);
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      return Promise.resolve(null); // already recording
    }

    setError(null);

    return navigator.mediaDevices.getUserMedia({ audio: true }).then(
      (stream) =>
        new Promise<Blob | null>((resolve) => {
          streamRef.current = stream;
          const mimeType = detectSupportedMimeType();
          const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
          recorderRef.current = recorder;
          chunksRef.current = [];

          recorder.ondataavailable = (e: BlobEvent) => {
            if (e.data.size > 0) chunksRef.current.push(e.data);
          };
          recorder.onstop = () => {
            const blob = new Blob(chunksRef.current, {
              type: recorder.mimeType || mimeType || "audio/webm",
            });
            chunksRef.current = [];
            teardown();
            setIsRecording(false);
            resolve(blob);
          };
          recorder.onerror = () => {
            setError("Recording failed.");
            teardown();
            setIsRecording(false);
            resolve(null);
          };

          recorder.start();
          setIsRecording(true);
          ceilingTimerRef.current = setTimeout(stop, MAX_DURATION_MS);
          armSilenceDetection(stream);
        }),
      (err) => {
        setError(isPermissionDenied(err) ? "Microphone access was denied." : "Couldn't access the microphone.");
        setIsRecording(false);
        return null;
      },
    );
  }, [isSupported, stop, teardown, armSilenceDetection]);

  useEffect(() => teardown, [teardown]);

  return { isSupported, isRecording, error, start, stop };
}
