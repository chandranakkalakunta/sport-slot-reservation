"""Code-owned email templates (ADR-0019 Decision 6).

Templates are pure functions returning a subject + HTML + plain-text part.
No per-tenant branding (logo/colors) — deferred until the subdomain work
(7.5) makes tenant-correct branding resolvable. All user-supplied values are
HTML-escaped before interpolation into the HTML part.
"""

from html import escape

from pydantic import BaseModel

_HTML_WRAPPER = """\
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 480px; \
margin: 0 auto; padding: 24px; color: #1a1a1a;">
{body}
<p style="margin-top: 32px; font-size: 12px; color: #888;">
{tenant_name} &middot; SportSlot Reservation
</p>
</div>
"""


class RenderedEmail(BaseModel):
    model_config = {"frozen": True}

    subject: str
    html: str
    text: str


def render_booking_confirmed(
    *,
    user_name: str,
    tenant_name: str,
    facility: str,
    sport: str,
    date: str,
    start_time: str,
    end_time: str,
    booking_id: str,
) -> RenderedEmail:
    e_user_name = escape(user_name)
    e_tenant_name = escape(tenant_name)
    e_facility = escape(facility)
    e_sport = escape(sport)
    e_date = escape(date)
    e_start_time = escape(start_time)
    e_end_time = escape(end_time)
    e_booking_id = escape(booking_id)

    subject = f"Booking confirmed: {facility} on {date}"

    body = f"""\
<h2 style="margin-top: 0;">Booking confirmed</h2>
<p>Hi {e_user_name},</p>
<p>Your booking at <strong>{e_tenant_name}</strong> is confirmed:</p>
<table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
<tr><td style="padding: 4px 0; color: #555;">Facility</td><td>{e_facility}</td></tr>
<tr><td style="padding: 4px 0; color: #555;">Sport</td><td>{e_sport}</td></tr>
<tr><td style="padding: 4px 0; color: #555;">Date</td><td>{e_date}</td></tr>
<tr><td style="padding: 4px 0; color: #555;">Time</td><td>{e_start_time} - {e_end_time}</td></tr>
<tr><td style="padding: 4px 0; color: #555;">Booking ID</td><td>{e_booking_id}</td></tr>
</table>
"""
    html = _HTML_WRAPPER.format(body=body, tenant_name=e_tenant_name)

    text = (
        f"Booking confirmed\n\n"
        f"Hi {user_name},\n\n"
        f"Your booking at {tenant_name} is confirmed:\n"
        f"Facility: {facility}\n"
        f"Sport: {sport}\n"
        f"Date: {date}\n"
        f"Time: {start_time} - {end_time}\n"
        f"Booking ID: {booking_id}\n\n"
        f"{tenant_name} - SportSlot Reservation\n"
    )

    return RenderedEmail(subject=subject, html=html, text=text)


def render_user_welcome(
    *,
    user_name: str,
    tenant_name: str,
    login_url: str,
    temp_password: str | None = None,
) -> RenderedEmail:
    e_user_name = escape(user_name)
    e_tenant_name = escape(tenant_name)
    e_login_url = escape(login_url)

    subject = f"Welcome to {tenant_name}"

    credentials_html = ""
    credentials_text = ""
    if temp_password:
        e_temp_password = escape(temp_password)
        credentials_html = (
            f'<p>Your temporary password: <strong>{e_temp_password}</strong></p>'
            f"<p>You'll be asked to change it on first login.</p>"
        )
        credentials_text = (
            f"Your temporary password: {temp_password}\n"
            f"You'll be asked to change it on first login.\n"
        )

    body = f"""\
<h2 style="margin-top: 0;">Welcome to {e_tenant_name}</h2>
<p>Hi {e_user_name},</p>
<p>Your account has been created.</p>
{credentials_html}
<p><a href="{e_login_url}" style="color: #1a73e8;">Sign in</a></p>
"""
    html = _HTML_WRAPPER.format(body=body, tenant_name=e_tenant_name)

    text = (
        f"Welcome to {tenant_name}\n\n"
        f"Hi {user_name},\n\n"
        f"Your account has been created.\n"
        f"{credentials_text}"
        f"Sign in: {login_url}\n\n"
        f"{tenant_name} - SportSlot Reservation\n"
    )

    return RenderedEmail(subject=subject, html=html, text=text)
