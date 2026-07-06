from sport_slot.notifications.email.templates import (
    render_booking_cancelled,
    render_booking_confirmed,
    render_user_welcome,
)


def test_booking_confirmed_subject_and_fields():
    r = render_booking_confirmed(
        user_name="Jane Doe",
        tenant_name="Honer Homes",
        facility="Tennis Court 1",
        sport="Tennis",
        date="2026-06-20",
        start_time="18:00",
        end_time="19:00",
        booking_id="bk-123",
    )
    assert r.subject == "Booking confirmed: Tennis Court 1 on 2026-06-20"
    for field in ("Jane Doe", "Honer Homes", "Tennis Court 1", "Tennis", "2026-06-20", "18:00", "19:00", "bk-123"):
        assert field in r.html
        assert field in r.text


def test_booking_confirmed_escapes_html():
    r = render_booking_confirmed(
        user_name="<script>alert(1)</script>",
        tenant_name="T&T Sports",
        facility="Court",
        sport="Squash",
        date="2026-06-20",
        start_time="18:00",
        end_time="19:00",
        booking_id="bk-1",
    )
    assert "<script>" not in r.html
    assert "&lt;script&gt;" in r.html
    assert "T&amp;T Sports" in r.html
    # Plain-text part is not HTML-escaped.
    assert "<script>alert(1)</script>" in r.text


def test_user_welcome_subject_and_fields():
    r = render_user_welcome(
        user_name="Resident One",
        tenant_name="Marina Towers",
        login_url="https://marina.example.com/login",
        temp_password="abc123XYZ",
    )
    assert r.subject == "Welcome to Marina Towers"
    for field in ("Resident One", "Marina Towers", "https://marina.example.com/login", "abc123XYZ"):
        assert field in r.html
        assert field in r.text


def test_user_welcome_without_temp_password_omits_credentials():
    r = render_user_welcome(
        user_name="Resident Two",
        tenant_name="Marina Towers",
        login_url="https://marina.example.com/login",
    )
    assert "temporary password" not in r.html.lower()
    assert "temporary password" not in r.text.lower()


def test_booking_cancelled_subject_and_fields():
    r = render_booking_cancelled(
        user_name="Jane Doe",
        tenant_name="Honer Homes",
        facility="Tennis Court 1",
        sport="Tennis",
        date="2026-08-15",
        start_time="18:00",
        booking_id="bk-456",
    )
    assert r.subject == "Booking cancelled: Tennis Court 1 on 2026-08-15"
    for field in ("Jane Doe", "Honer Homes", "Tennis Court 1", "Tennis", "2026-08-15",
                  "18:00", "bk-456"):
        assert field in r.html
        assert field in r.text


def test_booking_cancelled_facility_deactivated_shows_notice():
    r = render_booking_cancelled(
        user_name="Alice",
        tenant_name="Demo Society",
        facility="Court 1",
        sport="badminton",
        date="2026-08-15",
        start_time="09:00",
        booking_id="bk-789",
        reason="facility_deactivated",
    )
    assert "This facility is no longer available." in r.html
    assert "This facility is no longer available." in r.text


def test_booking_cancelled_other_reason_does_not_show_notice():
    """Raw reason codes other than 'facility_deactivated' are not shown to residents."""
    r = render_booking_cancelled(
        user_name="Bob",
        tenant_name="Demo Society",
        facility="Court 1",
        sport="badminton",
        date="2026-08-15",
        start_time="10:00",
        booking_id="bk-999",
        reason=None,
    )
    assert "no longer available" not in r.html
    assert "no longer available" not in r.text


def test_booking_cancelled_escapes_html():
    r = render_booking_cancelled(
        user_name="<script>alert(1)</script>",
        tenant_name="T&T Sports",
        facility="Court",
        sport="Squash",
        date="2026-08-15",
        start_time="10:00",
        booking_id="bk-xss",
    )
    assert "<script>" not in r.html
    assert "&lt;script&gt;" in r.html
    assert "T&amp;T Sports" in r.html
    assert "<script>alert(1)</script>" in r.text  # plain text not escaped


def test_user_welcome_escapes_html():
    r = render_user_welcome(
        user_name="<b>X</b>",
        tenant_name="Tenant",
        login_url="https://example.com",
        temp_password="<img src=x>",
    )
    assert "<b>X</b>" not in r.html
    assert "&lt;b&gt;X&lt;/b&gt;" in r.html
    assert "<img src=x>" not in r.html
    assert "&lt;img src=x&gt;" in r.html
