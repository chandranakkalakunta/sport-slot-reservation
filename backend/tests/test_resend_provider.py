import httpx
import pytest

from sport_slot.notifications.email.provider import EmailSendError
from sport_slot.notifications.email.resend_provider import (
    _RESEND_API_URL,
    ResendEmailProvider,
)


def test_missing_api_key_raises():
    with pytest.raises(EmailSendError):
        ResendEmailProvider(api_key=None)


def test_send_posts_expected_request_and_parses_id(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return httpx.Response(200, json={"id": "msg-1"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider(api_key="key-123", from_addr="no-reply@example.com")
    result = provider.send(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")

    assert captured["url"] == _RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer key-123"
    assert captured["json"]["from"] == "no-reply@example.com"
    assert captured["json"]["to"] == "user@example.com"
    assert captured["json"]["subject"] == "Hi"
    assert "tags" not in captured["json"]
    assert result.id == "msg-1"
    assert result.accepted is True
    assert result.provider == "resend"


def test_send_includes_tags_when_provided(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        return httpx.Response(200, json={"id": "msg-2"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider(api_key="key-123")
    provider.send(
        to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi",
        tags={"type": "booking_confirmed"},
    )

    assert captured["json"]["tags"] == [{"name": "type", "value": "booking_confirmed"}]


def test_send_raises_on_4xx(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return httpx.Response(422, text='{"message":"invalid recipient"}')

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider(api_key="key-123")
    with pytest.raises(EmailSendError, match="422"):
        provider.send(to="bad", subject="Hi", html="<p>hi</p>", text="hi")


def test_send_raises_on_5xx(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return httpx.Response(500, text="internal error")

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider(api_key="key-123")
    with pytest.raises(EmailSendError, match="500"):
        provider.send(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")


def test_send_raises_on_network_error(monkeypatch):
    def fake_post(url, json, headers, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider(api_key="key-123")
    with pytest.raises(EmailSendError, match="Resend request failed"):
        provider.send(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")
