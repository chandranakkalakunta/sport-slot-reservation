"""Provider-agnostic email sending interface (ADR-0019).

`EmailProvider` is the single seam between the notification pipeline and any
concrete vendor (Resend, Postmark, Brevo, ...). Swapping vendors is a single
new implementation of this Protocol, not a rewrite of call sites.
"""

from typing import Protocol

from pydantic import BaseModel


class EmailResult(BaseModel):
    """Outcome of a successful send."""

    model_config = {"frozen": True}

    id: str | None
    accepted: bool
    provider: str
    error: str | None = None


class EmailSendError(Exception):
    """Raised on a hard send failure (non-2xx response, network error, misconfiguration).

    No transient/permanent distinction is made here — the provider just
    signals success (EmailResult) or failure (this exception). Retry policy
    belongs to the caller (Cloud Tasks' built-in retry/backoff in 7.1.2), not
    the provider.
    """


class EmailProvider(Protocol):
    """Structural interface — concrete providers and test fakes both satisfy
    this without inheriting from it."""

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        tags: dict[str, str] | None = None,
    ) -> EmailResult:
        """Send one email. Raises EmailSendError on hard failure."""
        ...
