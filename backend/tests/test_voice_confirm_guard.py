"""Tests for the ADR-0036 D2 deterministic voice confirm/deny guard.

Sub-phase 1a scope: pure classification logic only, no endpoint/STT/TTS.
"""

from __future__ import annotations

import pytest

from sport_slot.services.voice.confirm_guard import ConfirmDecision, classify_confirmation

# ---------------------------------------------------------------------------
# Per-language: a clear affirmative and a clear negative, native script AND
# romanized, must classify correctly.
# ---------------------------------------------------------------------------

AFFIRM_CASES = [
    ("en", "yes", ConfirmDecision.AFFIRM),
    ("en", "okay", ConfirmDecision.AFFIRM),
    ("hi", "हाँ", ConfirmDecision.AFFIRM),
    ("hi", "haan", ConfirmDecision.AFFIRM),
    ("te", "అవును", ConfirmDecision.AFFIRM),
    ("te", "avunu", ConfirmDecision.AFFIRM),
    ("ta", "ஆம்", ConfirmDecision.AFFIRM),
    ("ta", "aam", ConfirmDecision.AFFIRM),
    ("kn", "ಹೌದು", ConfirmDecision.AFFIRM),
    ("kn", "haudu", ConfirmDecision.AFFIRM),
    ("ml", "അതെ", ConfirmDecision.AFFIRM),
    ("ml", "athe", ConfirmDecision.AFFIRM),
    ("mr", "होय", ConfirmDecision.AFFIRM),
    ("mr", "hoy", ConfirmDecision.AFFIRM),
    ("gu", "હા", ConfirmDecision.AFFIRM),
    ("gu", "haa", ConfirmDecision.AFFIRM),
    ("bn", "হ্যাঁ", ConfirmDecision.AFFIRM),
    ("bn", "hyan", ConfirmDecision.AFFIRM),
]

DENY_CASES = [
    ("en", "no", ConfirmDecision.DENY),
    ("en", "cancel", ConfirmDecision.DENY),
    ("hi", "नहीं", ConfirmDecision.DENY),
    ("hi", "nahi", ConfirmDecision.DENY),
    ("te", "వద్దు", ConfirmDecision.DENY),
    ("te", "vaddu", ConfirmDecision.DENY),
    ("ta", "இல்லை", ConfirmDecision.DENY),
    ("ta", "illai", ConfirmDecision.DENY),
    ("kn", "ಇಲ್ಲ", ConfirmDecision.DENY),
    ("kn", "illa", ConfirmDecision.DENY),
    ("ml", "ഇല്ല", ConfirmDecision.DENY),
    ("ml", "illa", ConfirmDecision.DENY),
    ("mr", "नाही", ConfirmDecision.DENY),
    ("mr", "nahi", ConfirmDecision.DENY),
    ("gu", "ના", ConfirmDecision.DENY),
    ("gu", "na", ConfirmDecision.DENY),
    ("bn", "না", ConfirmDecision.DENY),
    ("bn", "na", ConfirmDecision.DENY),
]


@pytest.mark.parametrize(("language", "transcript", "expected"), AFFIRM_CASES)
def test_clear_affirmative_per_language(language, transcript, expected):
    assert classify_confirmation(transcript, language) == expected


@pytest.mark.parametrize(("language", "transcript", "expected"), DENY_CASES)
def test_clear_negative_per_language(language, transcript, expected):
    assert classify_confirmation(transcript, language) == expected


# ---------------------------------------------------------------------------
# Multi-word phrases (native script and romanized) also classify correctly.
# ---------------------------------------------------------------------------


def test_multiword_affirm_phrase_english():
    assert classify_confirmation("go ahead", "en") == ConfirmDecision.AFFIRM
    assert classify_confirmation("please do", "en") == ConfirmDecision.AFFIRM


def test_multiword_deny_phrase_english():
    assert classify_confirmation("never mind", "en") == ConfirmDecision.DENY


def test_multiword_affirm_phrase_hindi():
    assert classify_confirmation("जी हाँ", "hi") == ConfirmDecision.AFFIRM
    assert classify_confirmation("theek hai", "hi") == ConfirmDecision.AFFIRM


# ---------------------------------------------------------------------------
# Fail-closed cases -> AMBIGUOUS.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("transcript", "language"),
    [
        ("", "en"),
        ("   ", "en"),
        ("yes", "fr"),
        ("yes", "xx"),
        ("yes no", "en"),
        ("avunu vaddu", "te"),
        ("book court two", "en"),
        ("haan nahi", "hi"),
    ],
)
def test_fail_closed_cases_are_ambiguous(transcript, language):
    assert classify_confirmation(transcript, language) == ConfirmDecision.AMBIGUOUS


def test_unsupported_language_ambiguous_even_with_valid_looking_transcript():
    # A transcript that would classify cleanly in en/hi must not leak a
    # decision for a language without a curated lexicon (ADR-0036 D3).
    assert classify_confirmation("yes", "fr") == ConfirmDecision.AMBIGUOUS
    assert classify_confirmation("oui", "fr") == ConfirmDecision.AMBIGUOUS


# ---------------------------------------------------------------------------
# Whole-word guard: a lexicon token appearing only as a substring of another
# word must NOT match — this is the property that rules out naive substring
# matching.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "transcript",
    [
        "nooo",  # contains "no" but is not the word "no"
        "oklahoma",  # contains "ok" but is not the word "ok"
        "correctness",  # contains "correct" but is not the word "correct"
        "yesterday",  # contains "yes" but is not the word "yes"
        "cancellation policy",  # contains "cancel" only as a prefix of another word
    ],
)
def test_whole_word_guard_rejects_substring_hits(transcript):
    assert classify_confirmation(transcript, "en") == ConfirmDecision.AMBIGUOUS


def test_whole_word_guard_still_matches_the_real_word_alongside_a_decoy():
    # Sanity check that the decoy words above aren't matching for some other
    # reason (e.g. lexicon change) — the real word still matches on its own.
    assert classify_confirmation("no", "en") == ConfirmDecision.DENY
    assert classify_confirmation("ok", "en") == ConfirmDecision.AFFIRM


# ---------------------------------------------------------------------------
# Two-sided falsifiability (§3.3): a naive substring-based baseline would
# false-AFFIRM on inputs the deterministic guard correctly rejects. This
# proves the guard does real safety work, not decoration.
# ---------------------------------------------------------------------------


def _naive_affirm_baseline(transcript: str) -> bool:
    """The unsafe check ADR-0036 D2 exists to replace: plain substring search."""
    return "yes" in transcript.lower()


@pytest.mark.parametrize(
    "transcript",
    [
        "yes, nevermind",  # contains "yes" but the user is actually declining
        "no, not yes I meant no",  # both present — must not silently pick a side
    ],
)
def test_naive_baseline_diverges_from_guard_on_adversarial_input(transcript):
    naive_result = _naive_affirm_baseline(transcript)
    guard_result = classify_confirmation(transcript, "en")

    # The naive check would wrongly treat this as an affirmative...
    assert naive_result is True
    # ...while the deterministic guard correctly refuses to affirm.
    assert guard_result in (ConfirmDecision.AMBIGUOUS, ConfirmDecision.DENY)
    assert guard_result != ConfirmDecision.AFFIRM
