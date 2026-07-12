"""Text-to-speech synthesis for the voice booking assistant.

ADR-0036 D1: TTS is the final stage of the speech → STT → translate →
agent → translate → TTS pipeline; this module implements ONLY the TTS
stage — turning the agent's reply prose into audio bytes. It must only
ever be fed the agent's already-prose reply text (see
services/voice/voice_pipeline.py) — never raw tool dispatch output.

ADR-0036 D5 / ADR-0037 D5′ (residency): Chirp 3 HD voices run on the
global/eu/us endpoints, not asia-south1 or asia-southeast1 — the same
documented residency exception already accepted for STT, extended here
to TTS. This module uses the default (global) `TextToSpeechClient`
endpoint; live-verified in sub-phase 1c (a real `en-IN-Chirp3-HD-Kore`
synthesis call, non-empty MP3 audio returned) before any pipeline code
was built on it — the same fail-fast discipline that caught the
withdrawn `chirp_3` / regional `chirp_2` STT issues.
"""

from __future__ import annotations

import structlog
from google.cloud import texttospeech

log = structlog.get_logger()

# Live-verified sub-phase 1c: en-IN-Chirp3-HD-Kore synthesizes real audio
# via the default (global) TextToSpeechClient endpoint. English-only
# today (ADR-0037) — see services/voice/languages.py for the staging seam.
_VOICE_NAME = "en-IN-Chirp3-HD-Kore"
_MIME = "audio/mpeg"


class TtsError(Exception):
    """Raised when the Text-to-Speech API call itself fails.

    A defined exception type so callers (services/voice/voice_pipeline.py)
    can degrade to a text-only reply on any failure, rather than crash the
    turn or leak an unclassified SDK exception.
    """


def synthesize(text: str, language_code: str) -> tuple[bytes, str]:
    """Synthesize `text` to speech. Returns (audio_bytes, mime_type).

    Raises `TtsError` on any SDK/API failure — this module does not
    swallow errors; the caller decides whether to degrade to text-only.
    `text` must already be natural prose (the agent's reply) — never raw
    tool dispatch output (e.g. key=value debug strings).
    """
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code, name=_VOICE_NAME
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    except Exception as exc:
        log.warning("tts_synthesize_error", error=str(exc), text_chars=len(text))
        raise TtsError(str(exc)) from exc

    log.info(
        "tts_synthesize_ok",
        text_chars=len(text),
        audio_bytes=len(response.audio_content),
    )
    return response.audio_content, _MIME
