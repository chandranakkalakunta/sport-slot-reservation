import pytest

from sport_slot.notifications.email.provider import EmailSendError
from tests.email_fakes import FakeEmailProvider


def test_fake_records_sent_messages():
    fake = FakeEmailProvider()
    result = fake.send(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")

    assert len(fake.sent) == 1
    assert fake.sent[0]["to"] == "user@example.com"
    assert fake.sent[0]["subject"] == "Hi"
    assert result.accepted is True
    assert result.provider == "fake"


def test_fake_simulates_failure():
    fake = FakeEmailProvider(fail=True)
    with pytest.raises(EmailSendError):
        fake.send(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")
    assert fake.sent == []
