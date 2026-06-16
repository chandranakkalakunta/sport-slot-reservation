"""Resend implementation of EmailProvider (ADR-0019 Decision 1).

Resend is the chosen vendor for its permanent free tier; it is reached only
through this class so swapping providers later is a single new
implementation, not a call-site rewrite.
"""

import httpx

from sport_slot.notifications.email.provider import EmailResult, EmailSendError

_RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_TIMEOUT_S = 10.0


class ResendEmailProvider:
    def __init__(
        self,
        api_key: str | None,
        from_addr: str = "no-reply@mail.chandraailabs.com",
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        if not api_key:
            raise EmailSendError("Resend API key is not configured")
        self._api_key = api_key
        self._from_addr = from_addr
        self._timeout = timeout

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        tags: dict[str, str] | None = None,
    ) -> EmailResult:
        body = {
            "from": self._from_addr,
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
        }
        if tags:
            body["tags"] = [{"name": k, "value": v} for k, v in tags.items()]

        try:
            response = httpx.post(
                _RESEND_API_URL,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise EmailSendError(f"Resend request failed: {exc}") from exc

        if response.status_code >= 400:
            raise EmailSendError(
                f"Resend returned {response.status_code}: {response.text}"
            )

        message_id = response.json().get("id")
        return EmailResult(id=message_id, accepted=True, provider="resend")
