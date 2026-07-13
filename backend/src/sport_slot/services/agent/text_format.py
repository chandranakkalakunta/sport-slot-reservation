"""Strip Markdown formatting syntax from agent reply text (AGENT-MD-TTS).

Applied once, at the reply boundary (orchestrator.run_agent /
run_agent_confirm), so both /agent/query (text) and /agent/voice (TTS)
get clean plain prose — Markdown emphasis read aloud as "asterisk
asterisk" otherwise. Formatting-only: never changes words, numbers,
punctuation, or line structure, only the Markdown syntax around them.
"""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^```[^\n]*\n?", re.MULTILINE)
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_BOLD_STAR_RE = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*", re.DOTALL)
_BOLD_UNDERSCORE_RE = re.compile(r"__(\S(?:.*?\S)?)__", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(\S(?:[^*\n]*?\S)?)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_(\S(?:[^_\n]*?\S)?)_(?!_)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
# Line-leading bullet marker only — a hyphen elsewhere on the line (e.g.
# "Tennis Court - 1") is content, not a bullet, and must survive untouched.
_BULLET_RE = re.compile(r"^([ \t]*)[*\-+][ \t]+", re.MULTILINE)


def to_plain_text(s: str | None) -> str:
    """Strip Markdown syntax from `s`, preserving content and line structure.

    None/empty -> "". Idempotent: calling twice is the same as calling once.
    """
    if not s:
        return ""
    text = s
    text = _FENCE_RE.sub("", text)
    text = text.replace("```", "")
    text = _HEADING_RE.sub("", text)
    text = _BOLD_STAR_RE.sub(r"\1", text)
    text = _BOLD_UNDERSCORE_RE.sub(r"\1", text)
    text = _ITALIC_STAR_RE.sub(r"\1", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _BULLET_RE.sub(r"\1- ", text)
    return text
