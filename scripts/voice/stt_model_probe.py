#!/usr/bin/env python3
"""LIVE diagnostic (read-only) — voice STT model x region x locale probe.

Sub-phase 1b hardcoded model="chirp_3" at locations/global, which the live
API rejects; chirp_3 STT was subsequently withdrawn entirely. The shipped
design (sub-phase 1c, ADR-0036/0037) is chirp_2 at a regional endpoint
(asia-southeast1) with a SINGLE language code (en-IN, English-first) — chirp_2
has no auto-detect, and the Speech-to-Text API caps any request at 3 language
codes regardless of model, so a request carrying more than 3 always 400s with
"Maximum number of allowed language codes is 3" (the exact bug that made the
1b version of this script useless: it sent all 9 candidate locales on every
row).

This script MEASURES which (model, location, language_codes) combinations
this project can actually reach, so the Coordinator/Strategist can validate
the shipped config and explore VOICE-ML candidates — it does not change
services/voice/stt.py and is not meant to be wired into any app path or CI
gate.

For each case in the matrix below, this attempts ONE sync Recognize call with
auto-decode + that case's language codes (<=3, always), and records whether
the request was accepted (got past model/location/locale validation) and, if
so, the transcript/detected language/confidence; if not, the FULL
(untruncated in the underlying report — only the printed table column is
clipped for readability) error string.

Usage (from repo root):
  cd backend
  uv run python ../scripts/voice/stt_model_probe.py --audio ../resources/voice_fixtures/synthetic_tone.wav

Real speech clips are NOT checked into git (resources/voice_fixtures/ only
tracks a .gitkeep) — record your own, e.g.:
  ffmpeg -f avfoundation -i ":0" -t 5 -ar 16000 -ac 1 resources/voice_fixtures/my_clip.wav
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

# The API rejects any request with more than 3 language codes — this is a
# hard ceiling, not a suggestion, regardless of model/location. Every case
# below respects it.
_MAX_LANGUAGE_CODES = 3


@dataclass(frozen=True)
class ProbeCase:
    label: str
    model: str
    location: str
    language_codes: list[str]

    def __post_init__(self) -> None:
        assert len(self.language_codes) <= _MAX_LANGUAGE_CODES, (
            f"{self.label}: {len(self.language_codes)} language codes > "
            f"{_MAX_LANGUAGE_CODES} — the API always 400s on this."
        )


# Case matrix. "global" uses the default (no regional) API endpoint; every
# other location uses its regional endpoint. chirp_3 is deliberately absent
# — it was withdrawn as an STT model, probing it is no longer meaningful.
_MATRIX: list[ProbeCase] = [
    # SHIPPED — the exact (model, location, language_codes) sub-phase 1c
    # runs in production today (services/voice/stt.py). This is the primary
    # case: if this row fails, voice STT itself is broken.
    ProbeCase("shipped config", "chirp_2", "asia-southeast1", ["en-IN"]),
    # Regional reachability — same model/locale, other candidate regions
    # (useful if asia-southeast1 ever needs to move).
    ProbeCase("chirp_2 reachability", "chirp_2", "us-central1", ["en-IN"]),
    ProbeCase("chirp_2 reachability", "chirp_2", "europe-west4", ["en-IN"]),
    # FUTURE VOICE-ML — multi-language candidates, capped at 3 codes as the
    # API requires. "long" is an auto-detect-capable model (unlike chirp_2)
    # and only reachable at non-regional endpoints; this is the control case
    # known to connect since the 1b live check.
    ProbeCase("future VOICE-ML (auto-detect candidate)", "long", "global", ["en-IN", "hi-IN", "te-IN"]),
    # Does regional chirp_2 accept multiple codes at all (no auto-detect,
    # but the API may still pick whichever code matches)?
    ProbeCase("future VOICE-ML (chirp_2, no auto-detect)", "chirp_2", "asia-southeast1", ["en-IN", "hi-IN", "te-IN"]),
]


def _client_for(location: str) -> speech_v2.SpeechClient:
    if location == "global":
        return speech_v2.SpeechClient()
    return speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{location}-speech.googleapis.com")
    )


def _probe(project: str, case: ProbeCase, audio_bytes: bytes) -> dict:
    client = _client_for(case.location)
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=case.language_codes,
        model=case.model,
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{project}/locations/{case.location}/recognizers/_",
        config=config,
        content=audio_bytes,
    )
    base = {
        "case": case.label,
        "model": case.model,
        "location": case.location,
        "codes": ",".join(case.language_codes),
    }
    try:
        response = client.recognize(request=request)
    except Exception as exc:  # noqa: BLE001 - diagnostic: capture everything, verbatim
        return {**base, "accepted": "N", "detected_lang": "", "confidence": "", "detail": str(exc)}

    if not response.results:
        return {
            **base,
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
        **base,
        "accepted": "Y",
        "detected_lang": result.language_code or "",
        "confidence": f"{confidence:.3f}" if confidence is not None else "",
        "detail": transcript,
    }


def _print_table(rows: list[dict]) -> None:
    columns = ["case", "model", "location", "codes", "accepted", "detected_lang", "confidence", "detail"]
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


_DEFAULT_AUDIO = Path("resources/voice_fixtures/synthetic_tone.wav")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--audio",
        default=str(_DEFAULT_AUDIO),
        help=(
            "Path to an audio clip to probe with (default: "
            f"{_DEFAULT_AUDIO} — NOT checked into git, see the module "
            "docstring for how to record one)"
        ),
    )
    parser.add_argument("--project", default="sport-slot-dev")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.is_file():
        if audio_path == _DEFAULT_AUDIO:
            print(
                f"ERROR: no audio clip found at the default path ({_DEFAULT_AUDIO}).\n"
                "Real speech clips are NOT checked into git (only "
                "resources/voice_fixtures/.gitkeep is tracked). Either:\n"
                "  - pass an existing clip:  --audio path/to/clip.wav\n"
                "  - record a quick one with ffmpeg (5s from the default mic):\n"
                f"      ffmpeg -f avfoundation -i \":0\" -t 5 -ar 16000 -ac 1 {_DEFAULT_AUDIO}\n",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: audio file not found: {audio_path}", file=sys.stderr)
        return 2
    audio_bytes = audio_path.read_bytes()

    clip_kind = "REAL SPEECH" if audio_path.name != _DEFAULT_AUDIO.name else "SYNTHETIC TONE (non-speech)"
    print(f"Clip used: {audio_path} [{clip_kind}]")
    print(
        "NOTE: with a synthetic/non-speech clip, only the 'accepted' column is "
        "meaningful — transcript/detected_lang/confidence require real speech.\n"
    )

    rows = [_probe(args.project, case, audio_bytes) for case in _MATRIX]
    _print_table(rows)

    print("\n=== Verbatim error bodies (untruncated) ===")
    for row in rows:
        if row["accepted"] == "N":
            print(f"\n--- {row['case']}: {row['model']} @ {row['location']} [{row['codes']}] ---")
            print(row["detail"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
