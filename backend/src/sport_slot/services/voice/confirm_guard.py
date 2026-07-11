"""Deterministic per-language confirm/deny guard for spoken confirmation turns.

ADR-0036 D2: the confirmation turn must not be a translate/LLM turn — a
mistranslated "no" would breach the propose-confirm-execute gate (ADR-0023).
This module extends ADR-0026 (deterministic Python guards over LLM judgment)
to a new case: confirmation interpretation. Matching is whole-word /
whole-phrase only, never naive substring, and fails closed to AMBIGUOUS on
any uncertainty (unsupported language, empty transcript, or a transcript
that matches both an affirm and a deny token).

Pure module: no I/O, no logging, no network calls. Sub-phase 1a scope only —
no endpoint wiring here (see ADR-0036 D7 for sub-phase 1b).
"""

from __future__ import annotations

import re
from enum import Enum

from sport_slot.services.voice.confirm_lexicon_data import CONFIRM_LEXICON


class ConfirmDecision(str, Enum):
    """Outcome of classify_confirmation. AMBIGUOUS means: re-prompt, never guess."""

    AFFIRM = "affirm"
    DENY = "deny"
    AMBIGUOUS = "ambiguous"


_STRIP_CHARS = " \t\n\r.,!?;:\"'()[]{}।"


def _normalize(transcript: str) -> str:
    """Casefold, collapse internal whitespace, strip surrounding punctuation."""
    normalized = re.sub(r"\s+", " ", transcript.strip().casefold())
    return normalized.strip(_STRIP_CHARS)


def _tokenize(normalized: str) -> list[str]:
    """Split into whole-word tokens, stripping punctuation from each.

    Deliberately NOT regex `\\b`-based: Python's `\\w` excludes Unicode
    combining marks (category Mn/Mc), which several supported scripts use
    for vowel signs and anusvara/candrabindu (e.g. Devanagari `नहीं`). A
    `\\b`-based match silently breaks mid-word on those scripts. Splitting on
    whitespace and stripping punctuation per token avoids that failure mode
    while still rejecting naive substring hits (e.g. "no" inside "nooo").
    """
    return [tok for raw in normalized.split(" ") if (tok := raw.strip(_STRIP_CHARS))]


def _contains_phrase(tokens: list[str], phrase: str) -> bool:
    """True if `phrase` (one or more words) appears as a contiguous run in tokens."""
    phrase_tokens = phrase.casefold().split(" ")
    n = len(phrase_tokens)
    return any(tokens[i : i + n] == phrase_tokens for i in range(len(tokens) - n + 1))


def _any_match(tokens: list[str], phrases: list[str]) -> bool:
    return any(_contains_phrase(tokens, phrase) for phrase in phrases)


def classify_confirmation(transcript: str, language: str) -> ConfirmDecision:
    """Classify a spoken confirmation utterance. Fail-closed on any doubt.

    ADR-0036 D2 / ADR-0026. Pure, deterministic — no LLM participates in this
    decision. Decision matrix:

      - language not in the curated lexicon -> AMBIGUOUS
      - empty / whitespace-only transcript   -> AMBIGUOUS
      - both an affirm and a deny hit        -> AMBIGUOUS
      - only a deny hit                      -> DENY
      - only an affirm hit                   -> AFFIRM
      - neither                              -> AMBIGUOUS
    """
    if language not in CONFIRM_LEXICON:
        return ConfirmDecision.AMBIGUOUS

    normalized = _normalize(transcript)
    if not normalized:
        return ConfirmDecision.AMBIGUOUS

    tokens = _tokenize(normalized)
    lexicon = CONFIRM_LEXICON[language]
    affirm_hit = _any_match(tokens, lexicon["affirm"])
    deny_hit = _any_match(tokens, lexicon["deny"])

    if affirm_hit and deny_hit:
        return ConfirmDecision.AMBIGUOUS
    if deny_hit:
        return ConfirmDecision.DENY
    if affirm_hit:
        return ConfirmDecision.AFFIRM
    return ConfirmDecision.AMBIGUOUS
