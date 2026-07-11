"""Speech-to-text ingestion for the voice booking assistant.

ADR-0036 D1: STT is the first stage of the speech → STT → translate →
agent → translate → TTS pipeline; this module implements ONLY the STT
stage — turning raw audio bytes into a transcript, a detected language,
and a confidence score. No translation, no agent wiring, no TTS, and no
call into the confirm/deny guard (services/voice/confirm_guard.py)
happen here — those are sub-phase 1c.

ADR-0036 D3: language detection is conditioned on the nine curated
candidate locales (the same language set the confirm/deny guard
curates — see `confirm_lexicon_data.CONFIRM_LEXICON` for the single
source of truth on which languages are "supported").

ADR-0036 D5: Chirp 3 (the model tier with natural Indic-language
support) is not available in asia-south1, so this module deliberately
targets the `global` Speech-to-Text recognizer endpoint — a documented,
accepted residency exception, not an oversight.
"""

from __future__ import annotations

import time
from typing import NamedTuple

import structlog
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

from sport_slot.config import get_settings
from sport_slot.services.voice.confirm_lexicon_data import CONFIRM_LEXICON

log = structlog.get_logger()

# ADR-0036 D5: global is the accepted residency exception for Chirp 3.
_RECOGNIZER_LOCATION = "global"
_MODEL = "chirp_3"

# ADR-0036 D3: the nine curated candidate locales, condition detection on
# these only. Kept in "-IN" BCP-47 form here because that is what the
# Speech-to-Text API's `language_codes` config expects; the 2-letter
# "supported" set is the normalized form of the same list.
_CANDIDATE_LOCALES: tuple[str, ...] = (
    "en-IN",
    "hi-IN",
    "te-IN",
    "ta-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "gu-IN",
    "bn-IN",
)

# Single source of truth for "is this language supported" — the same nine
# languages the confirm/deny guard curates (ADR-0036 D3).
_SUPPORTED_LANGUAGES: frozenset[str] = frozenset(CONFIRM_LEXICON.keys())


class SttError(Exception):
    """Raised when the Speech-to-Text API call itself fails.

    A defined exception type so callers (sub-phase 1c) can catch one
    stable type regardless of the underlying SDK's exception hierarchy.
    """


class SttResult(NamedTuple):
    """Result of one STT call. `language` is None when nothing was
    detected (e.g. no results at all); `is_supported_language` is only
    ever True for one of the nine ADR-0036 D3 languages.
    """

    transcript: str
    language: str | None
    raw_language: str | None
    confidence: float | None
    is_supported_language: bool


def _normalize_language(raw_language: str) -> str:
    """BCP-47 (e.g. "te-IN") -> 2-letter language code (e.g. "te")."""
    return raw_language.split("-")[0].lower()


def _empty_result() -> SttResult:
    return SttResult(
        transcript="", language=None, raw_language=None,
        confidence=None, is_supported_language=False,
    )


def _recognizer_path(project: str) -> str:
    return f"projects/{project}/locations/{_RECOGNIZER_LOCATION}/recognizers/_"


def transcribe(audio_bytes: bytes) -> SttResult:
    """Transcribe `audio_bytes` via Speech-to-Text V2 (sync `recognize`).

    Auto-decodes the container (WebM/Opus, MP4/AAC, etc. — ADR-0036
    context: browser audio arrives in different containers depending on
    client platform) via `AutoDetectDecodingConfig`, so no fixed
    encoding is assumed. Raises `SttError` on any SDK/API failure —
    never a bare, unclassified exception. An empty result set (nothing
    recognized) is not an error: it returns an empty `SttResult`.
    """
    settings = get_settings()
    client = speech_v2.SpeechClient()

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=list(_CANDIDATE_LOCALES),
        model=_MODEL,
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=_recognizer_path(settings.gcp_project),
        config=config,
        content=audio_bytes,
    )

    started = time.monotonic()
    try:
        response = client.recognize(request=request)
    except Exception as exc:
        log.warning("stt_transcribe_error", error=str(exc))
        raise SttError(str(exc)) from exc
    duration_ms = int((time.monotonic() - started) * 1000)

    if not response.results:
        log.info("stt_transcribe_empty", duration_ms=duration_ms)
        return _empty_result()

    result = response.results[0]
    raw_language = result.language_code or None
    language = _normalize_language(raw_language) if raw_language else None
    is_supported = language in _SUPPORTED_LANGUAGES if language else False

    alternatives = result.alternatives
    transcript = alternatives[0].transcript if alternatives else ""
    confidence = getattr(alternatives[0], "confidence", None) if alternatives else None

    log.info(
        "stt_transcribe_ok",
        duration_ms=duration_ms,
        detected_language=raw_language,
        transcript_chars=len(transcript),
        is_supported_language=is_supported,
    )

    return SttResult(
        transcript=transcript,
        language=language,
        raw_language=raw_language,
        confidence=confidence,
        is_supported_language=is_supported,
    )
