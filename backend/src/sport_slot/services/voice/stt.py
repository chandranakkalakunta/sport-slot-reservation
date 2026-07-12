"""Speech-to-text ingestion for the voice booking assistant.

ADR-0036 D1: STT is the first stage of the speech → STT → translate →
agent → translate → TTS pipeline; this module implements ONLY the STT
stage — turning raw audio bytes into a transcript, a detected language,
and a confidence score. No translation, no agent wiring, no TTS, and no
call into the confirm/deny guard (services/voice/confirm_guard.py)
happen here — those are sub-phase 1c.

ADR-0037 D3′ (supersedes ADR-0036 D3): candidate-list auto-detection on
this API is capped at 3 language codes, and is only available at the
eu/global/us multi-region endpoints — the platform's full nine-language
set cannot be sent in one call. The caller (sub-phase 1c) is therefore
responsible for passing the calling resident's TENANT's configured
candidate trio (1–3 BCP-47 codes); this module only validates the count
and sends exactly what it is given. The nine-language platform set
(`confirm_lexicon_data.CONFIRM_LEXICON`) remains the source of truth for
`is_supported_language`, independent of which trio was requested.

ADR-0037 (model & endpoint, supersedes ADR-0036 D5): `chirp_3` was
found to be withdrawn (GA-revoked) via live testing in sub-phase 1b —
`chirp_2` (GA) is used instead. Candidate-list auto-detection is only
offered at the eu/global/us multi-region endpoints (the Asia GA
endpoints accept a single language code only, no auto-detect), so this
module targets the `global` recognizer endpoint. This is a permanent
residency exception (ADR-0037 D5′), not improvable to an in-Asia region
under this detection strategy.
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

# ADR-0037: global multi-region endpoint — required for candidate-list
# auto-detection (eu/global/us only); chirp_2 is GA here.
_RECOGNIZER_LOCATION = "global"
_MODEL = "chirp_2"

# ADR-0037 D3′: the API caps candidate-list auto-detection at 3 codes.
_MAX_CANDIDATE_CODES = 3

# Single source of truth for "is this language supported" — the platform's
# full nine-language set (ADR-0036 D3 / ADR-0037 D3′), independent of which
# ≤3-code candidate trio a given call actually sent.
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


def transcribe(audio_bytes: bytes, language_codes: list[str]) -> SttResult:
    """Transcribe `audio_bytes` via Speech-to-Text V2 (sync `recognize`).

    `language_codes` is the calling resident's tenant's configured
    candidate trio (ADR-0037 D3′) — 1 to 3 BCP-47 codes (e.g.
    ["en-IN", "hi-IN", "te-IN"]); Speech-to-Text auto-detects among
    them. Raises `SttError` if the count is outside 1..3 — the API
    enforces this cap and a call outside it can never succeed.

    Auto-decodes the container (WebM/Opus, MP4/AAC, etc. — ADR-0036
    context: browser audio arrives in different containers depending on
    client platform) via `AutoDetectDecodingConfig`, so no fixed
    encoding is assumed. Raises `SttError` on any SDK/API failure —
    never a bare, unclassified exception. An empty result set (nothing
    recognized) is not an error: it returns an empty `SttResult`.
    """
    if not 1 <= len(language_codes) <= _MAX_CANDIDATE_CODES:
        raise SttError(
            f"language_codes must have between 1 and {_MAX_CANDIDATE_CODES} "
            f"entries, got {len(language_codes)}"
        )

    settings = get_settings()
    client = speech_v2.SpeechClient()

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=language_codes,
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
