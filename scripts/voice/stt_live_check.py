#!/usr/bin/env python3
"""Voice I/O sub-phase 1b — LIVE STT measurement harness (Coordinator/ADC-run).

This is a measurement tool, not a CI gate: it calls the REAL Speech-to-Text
API (services/voice/stt.transcribe) over a directory of audio fixtures and
prints one table row per file, so the Coordinator can measure — on real
audio — whether cross-container decode (WebM/Opus vs MP4/AAC) works and how
reliable language detection + confidence are on Indic-language clips. That
measurement is what sub-phase 1c's fallback logic will be designed against.

Usage (from repo root):
  cd backend && uv run python ../scripts/voice/stt_live_check.py \
      --fixtures-dir ../resources/voice_fixtures

Requires: Application Default Credentials for a principal with
`roles/speech.client` (or equivalent) on the target project, and the
Speech-to-Text API enabled on that project (see ADR-0036 sub-phase 1b).

Cross-container fixture generation: if `ffmpeg` is on PATH AND
<fixtures-dir>/src.wav exists, this script derives src.webm (libopus) and
src.m4a (aac) from it before the run, to prove auto-decode works across
containers. If either precondition is missing, generation is skipped with
a printed note, and the script simply runs over whatever audio files are
already present in the directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_AUDIO_EXTENSIONS = (".wav", ".webm", ".m4a", ".mp3", ".flac", ".ogg")


def _generate_cross_container_fixtures(fixtures_dir: Path) -> None:
    """Derive src.webm and src.m4a from src.wav via ffmpeg, if possible."""
    ffmpeg_path = shutil.which("ffmpeg")
    src_wav = fixtures_dir / "src.wav"

    if ffmpeg_path is None:
        print("NOTE: ffmpeg not found on PATH — skipping cross-container fixture generation.")
        return
    if not src_wav.exists():
        print(f"NOTE: {src_wav} not found — skipping cross-container fixture generation.")
        return

    derivations = [
        (fixtures_dir / "src.webm", ["-c:a", "libopus"]),
        (fixtures_dir / "src.m4a", ["-c:a", "aac"]),
    ]
    for out_path, codec_args in derivations:
        cmd = [ffmpeg_path, "-y", "-i", str(src_wav), *codec_args, str(out_path)]
        print(f"Generating {out_path.name} via: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True)


def _run_transcribe(path: Path) -> dict:
    """Import deferred to keep --help usable without backend deps installed."""
    from sport_slot.services.voice.stt import SttError, transcribe

    audio_bytes = path.read_bytes()
    try:
        result = transcribe(audio_bytes)
    except SttError as exc:
        return {
            "file": path.name,
            "container": path.suffix.lstrip("."),
            "transcript": "",
            "detected_lang": "",
            "confidence": "",
            "ok": f"ERROR: {exc}",
        }
    return {
        "file": path.name,
        "container": path.suffix.lstrip("."),
        "transcript": result.transcript,
        "detected_lang": result.raw_language or "",
        "confidence": f"{result.confidence:.3f}" if result.confidence is not None else "",
        "ok": "OK" if result.transcript else "EMPTY",
    }


def _print_table(rows: list[dict]) -> None:
    columns = ["file", "container", "transcript", "detected_lang", "confidence", "ok"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns} if rows else {
        c: len(c) for c in columns
    }

    def _fmt_row(values: dict) -> str:
        return " | ".join(str(values[c]).ljust(widths[c]) for c in columns)

    header = {c: c for c in columns}
    print(_fmt_row(header))
    print("-+-".join("-" * widths[c] for c in columns))
    for row in rows:
        print(_fmt_row(row))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-dir",
        default="resources/voice_fixtures",
        help="Directory of audio fixtures to transcribe (default: resources/voice_fixtures)",
    )
    args = parser.parse_args()
    fixtures_dir = Path(args.fixtures_dir)

    if not fixtures_dir.is_dir():
        print(f"NOTE: fixtures directory {fixtures_dir} does not exist — nothing to run.")
        return 0

    _generate_cross_container_fixtures(fixtures_dir)

    files = sorted(
        p for p in fixtures_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _AUDIO_EXTENSIONS
    )
    if not files:
        print(f"NOTE: no audio fixtures found in {fixtures_dir} — nothing to run.")
        return 0

    rows = [_run_transcribe(path) for path in files]
    _print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
