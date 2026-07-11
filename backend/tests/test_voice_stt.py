"""Hermetic tests for the ADR-0036 D1 STT ingestion module.

No real API calls: `speech_v2.SpeechClient` is always mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sport_slot.services.voice.stt import SttError, SttResult, transcribe

_CLIENT_PATH = "sport_slot.services.voice.stt.speech_v2.SpeechClient"


def _alternative(transcript: str, confidence: float | None = None) -> SimpleNamespace:
    return SimpleNamespace(transcript=transcript, confidence=confidence)


def _result(language_code: str | None, alternatives: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(language_code=language_code, alternatives=alternatives)


def _response(results: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(results=results)


def _mock_client(response: SimpleNamespace | None = None, side_effect: Exception | None = None):
    client = MagicMock()
    if side_effect is not None:
        client.recognize.side_effect = side_effect
    else:
        client.recognize.return_value = response
    return client


# ---------------------------------------------------------------------------
# Normal parsing
# ---------------------------------------------------------------------------


def test_normal_result_parsed_correctly():
    response = _response([_result("te-IN", [_alternative("avunu", 0.92)])])
    with patch(_CLIENT_PATH, return_value=_mock_client(response)):
        result = transcribe(b"audio-bytes")

    assert result == SttResult(
        transcript="avunu",
        language="te",
        raw_language="te-IN",
        confidence=0.92,
        is_supported_language=True,
    )


def test_request_is_built_with_expected_recognizer_config():
    response = _response([_result("en-IN", [_alternative("yes", 0.9)])])
    mock_client = _mock_client(response)
    with patch(_CLIENT_PATH, return_value=mock_client):
        transcribe(b"audio-bytes")

    request = mock_client.recognize.call_args.kwargs["request"]
    assert request.recognizer.endswith("/locations/global/recognizers/_")
    assert request.config.model == "chirp_3"
    assert list(request.config.language_codes) == [
        "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN", "mr-IN", "gu-IN", "bn-IN",
    ]
    assert request.content == b"audio-bytes"


# ---------------------------------------------------------------------------
# BCP-47 -> 2-letter normalization + unsupported-language flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_language", "expected_2letter", "expected_supported"),
    [
        ("te-IN", "te", True),
        ("hi-IN", "hi", True),
        ("en-IN", "en", True),
        ("bn-IN", "bn", True),
        ("fr-FR", "fr", False),  # outside the 9 curated languages
        ("de-DE", "de", False),
    ],
)
def test_bcp47_normalization_and_supported_flag(raw_language, expected_2letter, expected_supported):
    response = _response([_result(raw_language, [_alternative("hello", 0.5)])])
    with patch(_CLIENT_PATH, return_value=_mock_client(response)):
        result = transcribe(b"audio-bytes")

    assert result.raw_language == raw_language
    assert result.language == expected_2letter
    assert result.is_supported_language is expected_supported


# ---------------------------------------------------------------------------
# Empty / no-result handling — must not raise
# ---------------------------------------------------------------------------


def test_empty_results_returns_empty_sttresult_without_raising():
    with patch(_CLIENT_PATH, return_value=_mock_client(_response([]))):
        result = transcribe(b"silence")

    assert result == SttResult(
        transcript="", language=None, raw_language=None,
        confidence=None, is_supported_language=False,
    )


def test_result_with_no_alternatives_yields_empty_transcript_and_confidence():
    response = _response([_result("hi-IN", [])])
    with patch(_CLIENT_PATH, return_value=_mock_client(response)):
        result = transcribe(b"audio-bytes")

    assert result.transcript == ""
    assert result.confidence is None
    # Language is still reported from the result even with no alternatives.
    assert result.language == "hi"


# ---------------------------------------------------------------------------
# Confidence handling — Chirp may omit it
# ---------------------------------------------------------------------------


def test_confidence_none_when_omitted_by_api():
    response = _response([_result("ta-IN", [_alternative("aam", confidence=None)])])
    with patch(_CLIENT_PATH, return_value=_mock_client(response)):
        result = transcribe(b"audio-bytes")

    assert result.confidence is None
    assert result.transcript == "aam"


# ---------------------------------------------------------------------------
# Error propagation — a defined exception type, never a bare crash
# ---------------------------------------------------------------------------


def test_sdk_error_propagates_as_defined_sttexception():
    with patch(_CLIENT_PATH, return_value=_mock_client(side_effect=RuntimeError("boom"))):
        with pytest.raises(SttError) as exc_info:
            transcribe(b"audio-bytes")

    assert "boom" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)
