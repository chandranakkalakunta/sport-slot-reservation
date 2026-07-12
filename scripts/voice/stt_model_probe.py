#!/usr/bin/env python3
"""THROWAWAY diagnostic (read-only) — Voice I/O 1b model x region probe.

Sub-phase 1b hardcoded model="chirp_3" at locations/global, which the live
API rejects. This script MEASURES which (model, location) combinations this
project can actually reach, so the Coordinator/Strategist can pick one — it
does not change services/voice/stt.py and is not meant to be wired into any
app path or CI gate.

For each (model, location) in the matrix below, this attempts ONE sync
Recognize call with auto-decode + the candidate locale list, and records
whether the request was accepted (got past model/location validation) and,
if so, the transcript/detected language/confidence; if not, the FULL
(untruncated in the underlying report — only the printed table column is
clipped for readability) error string.

Usage (from repo root):
  cd backend && uv run python ../scripts/voice/stt_model_probe.py \
      --audio ../resources/voice_fixtures/synthetic_tone.wav
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

_CANDIDATE_LOCALES = [
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN", "mr-IN", "gu-IN", "bn-IN", "auto",
]

# (model, location) matrix under test. "global" uses the default (no
# regional) API endpoint; every other location uses its regional endpoint.
_MATRIX: list[tuple[str, str]] = [
    ("chirp_2", "asia-southeast1"),
    ("chirp_2", "us-central1"),
    ("chirp_2", "europe-west4"),
    ("chirp_3", "asia-south1"),
    ("chirp_3", "europe-west2"),
    ("long", "global"),  # control — known to connect (1b live check)
]


def _client_for(location: str) -> speech_v2.SpeechClient:
    if location == "global":
        return speech_v2.SpeechClient()
    return speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{location}-speech.googleapis.com")
    )


def _probe(project: str, model: str, location: str, audio_bytes: bytes) -> dict:
    client = _client_for(location)
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=_CANDIDATE_LOCALES,
        model=model,
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{project}/locations/{location}/recognizers/_",
        config=config,
        content=audio_bytes,
    )
    try:
        response = client.recognize(request=request)
    except Exception as exc:  # noqa: BLE001 - diagnostic: capture everything, verbatim
        return {
            "model": model,
            "location": location,
            "accepted": "N",
            "detected_lang": "",
            "confidence": "",
            "detail": str(exc),
        }

    if not response.results:
        return {
            "model": model,
            "location": location,
            "accepted": "Y",
            "detected_lang": "",
            "confidence": "",
            "detail": "(accepted, empty results)",
        }

    result = response.results[0]
    alternatives = result.alternatives
    transcript = alternatives[0].transcript if alternatives else ""
    confidence = getattr(alternatives[0], "confidence", None) if alternatives else None
    return {
        "model": model,
        "location": location,
        "accepted": "Y",
        "detected_lang": result.language_code or "",
        "confidence": f"{confidence:.3f}" if confidence is not None else "",
        "detail": transcript,
    }


def _print_table(rows: list[dict]) -> None:
    columns = ["model", "location", "accepted", "detected_lang", "confidence", "detail"]
    display_rows = [
        {**r, "detail": (r["detail"][:200] + ("..." if len(r["detail"]) > 200 else ""))}
        for r in rows
    ]
    widths = {c: max(len(c), *(len(str(r[c])) for r in display_rows)) for c in columns}

    def _fmt(values: dict) -> str:
        return " | ".join(str(values[c]).ljust(widths[c]) for c in columns)

    print(_fmt({c: c for c in columns}))
    print("-+-".join("-" * widths[c] for c in columns))
    for row in display_rows:
        print(_fmt(row))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio",
        default="resources/voice_fixtures/synthetic_tone.wav",
        help="Path to an audio clip to probe with (default: synthetic tone fixture)",
    )
    parser.add_argument("--project", default="sport-slot-dev")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.is_file():
        print(f"ERROR: audio file not found: {audio_path}", file=sys.stderr)
        return 2
    audio_bytes = audio_path.read_bytes()

    clip_kind = "REAL SPEECH" if audio_path.name != "synthetic_tone.wav" else "SYNTHETIC TONE (non-speech)"
    print(f"Clip used: {audio_path} [{clip_kind}]")
    print(
        "NOTE: with a synthetic/non-speech clip, only the 'accepted' column is "
        "meaningful — transcript/detected_lang/confidence require real speech.\n"
    )

    rows = [_probe(args.project, model, location, audio_bytes) for model, location in _MATRIX]
    _print_table(rows)

    print("\n=== Verbatim error bodies (untruncated) ===")
    for row in rows:
        if row["accepted"] == "N":
            print(f"\n--- {row['model']} @ {row['location']} ---")
            print(row["detail"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
