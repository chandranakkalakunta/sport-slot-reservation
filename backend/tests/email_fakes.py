"""Test double for EmailProvider — no network, records every send() call."""

from sport_slot.notifications.email.provider import EmailResult, EmailSendError


class FakeEmailProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict] = []

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        tags: dict[str, str] | None = None,
    ) -> EmailResult:
        if self.fail:
            raise EmailSendError("FakeEmailProvider configured to fail")
        self.sent.append(
            {"to": to, "subject": subject, "html": html, "text": text, "tags": tags}
        )
        return EmailResult(id=f"fake-{len(self.sent)}", accepted=True, provider="fake")
