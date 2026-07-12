"""Hermetic tests for the ADR-0036/0037 TTS synthesis module.

No real API calls: `texttospeech.TextToSpeechClient` is always mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sport_slot.services.voice.tts import TtsError, synthesize

_CLIENT_PATH = "sport_slot.services.voice.tts.texttospeech.TextToSpeechClient"


def _mock_client(audio_content: bytes | None = None, side_effect: Exception | None = None):
    client = MagicMock()
    if side_effect is not None:
        client.synthesize_speech.side_effect = side_effect
    else:
        client.synthesize_speech.return_value = SimpleNamespace(audio_content=audio_content)
    return client


def test_synthesize_returns_audio_bytes_and_mime():
    with patch(_CLIENT_PATH, return_value=_mock_client(b"\xff\xf3fake-mp3-bytes")):
        audio, mime = synthesize("Your booking is confirmed.", "en-IN")

    assert audio == b"\xff\xf3fake-mp3-bytes"
    assert mime == "audio/mpeg"


def test_synthesize_passes_text_and_language_to_the_request():
    mock_client = _mock_client(b"audio")
    with patch(_CLIENT_PATH, return_value=mock_client):
        synthesize("Hello there.", "en-IN")

    kwargs = mock_client.synthesize_speech.call_args.kwargs
    assert kwargs["input"].text == "Hello there."
    assert kwargs["voice"].language_code == "en-IN"
    assert kwargs["voice"].name == "en-IN-Chirp3-HD-Kore"


def test_sdk_error_propagates_as_defined_ttsexception():
    with patch(_CLIENT_PATH, return_value=_mock_client(side_effect=RuntimeError("boom"))):
        with pytest.raises(TtsError) as exc_info:
            synthesize("Hello there.", "en-IN")

    assert "boom" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)
