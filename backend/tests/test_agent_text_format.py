"""AGENT-MD-TTS: to_plain_text strips Markdown syntax, preserves content."""

from sport_slot.services.agent.text_format import to_plain_text


def test_bold_star_stripped():
    assert to_plain_text("**bold**") == "bold"


def test_bold_underscore_stripped():
    assert to_plain_text("__bold__") == "bold"


def test_italic_star_stripped():
    assert to_plain_text("*italic*") == "italic"


def test_italic_underscore_stripped():
    assert to_plain_text("_italic_") == "italic"


def test_heading_stripped():
    assert to_plain_text("# Heading") == "Heading"
    assert to_plain_text("## Sub-heading") == "Sub-heading"


def test_inline_code_stripped():
    assert to_plain_text("Run `list_bookings` now") == "Run list_bookings now"


def test_code_fence_stripped():
    assert to_plain_text("```\ncode block\n```") == "code block\n"


def test_bullet_markers_normalized_to_dash():
    assert to_plain_text("* one\n- two\n+ three") == "- one\n- two\n- three"


def test_court_hyphen_is_content_not_bullet():
    """A hyphen surrounded by spaces mid-line is content, never a bullet."""
    assert to_plain_text("Tennis Court - 1") == "Tennis Court - 1"


def test_bookings_list_example():
    raw = (
        "Here are your upcoming bookings:\n\n"
        "* **Badminton Court - 1**:\n"
        "* Monday, July 13, 2026 at 19:00"
    )
    expected = (
        "Here are your upcoming bookings:\n\n"
        "- Badminton Court - 1:\n"
        "- Monday, July 13, 2026 at 19:00"
    )
    assert to_plain_text(raw) == expected


def test_rupee_amounts_and_dates_preserved():
    text = "Your charge for June 2026 is ₹1,250.00, due July 5, 2026 at 19:00."
    assert to_plain_text(text) == text


def test_line_breaks_preserved():
    text = "Line one.\nLine two.\n\nLine four."
    assert to_plain_text(text) == text


def test_plain_text_passes_through_unchanged():
    text = "Booked Tennis Court - 1 on 2026-07-14 at 18:00."
    assert to_plain_text(text) == text


def test_empty_string_is_safe():
    assert to_plain_text("") == ""


def test_none_is_safe():
    assert to_plain_text(None) == ""


def test_idempotent():
    raw = "* **Badminton Court - 1**:\n* Monday, July 13, 2026 at 19:00"
    once = to_plain_text(raw)
    twice = to_plain_text(once)
    assert once == twice
