"""Mail gateway (us-5): SMTP to Mailpit in the MVP, Gmail and Graph
implementations post-MVP behind the same interface (mvp.md).

Messages are built with the stdlib ``email`` package: no model output is
ever rendered as HTML (prompt-injection rule, ADR 0008) — the pipeline
sends plain text only.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib


class MailSendError(RuntimeError):
    """The gateway refused or failed the delivery. The message is safe to
    show to the user; nothing was sent."""


@dataclass(frozen=True)
class Attachment:
    """One file to attach, already decrypted in memory. Size limits are a
    provider concern enforced before the gateway is called."""

    filename: str
    content: bytes
    mimetype: str


@dataclass(frozen=True)
class OutgoingMail:
    sender: str
    recipient: str
    subject: str
    text_body: str
    attachments: tuple[Attachment, ...] = ()


@dataclass(frozen=True)
class SentMail:
    provider: str
    message_id: str | None
    """Provider's id for the stored message; SMTP servers may not give one."""

    thread_id: str | None
    """Provider thread id when the provider threads messages (post-MVP)."""


class MailGateway(Protocol):
    async def send(self, mail: OutgoingMail) -> SentMail:
        """Deliver one message or raise MailSendError."""


def build_message(mail: OutgoingMail) -> EmailMessage:
    """Pure message construction — unit-tested without a server."""
    message = EmailMessage()
    message["From"] = mail.sender
    message["To"] = mail.recipient
    message["Subject"] = mail.subject
    message.set_content(mail.text_body)
    for attachment in mail.attachments:
        maintype, _, subtype = attachment.mimetype.partition("/")
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )
    return message


class SmtpMailGateway:
    """aiosmtplib implementation. Dev and the jury demo target Mailpit
    (no TLS, no auth); production replaces this class per mvp.md."""

    def __init__(self, *, host: str, port: int, timeout_seconds: float = 10.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout_seconds

    async def send(self, mail: OutgoingMail) -> SentMail:
        smtp = aiosmtplib.SMTP(
            hostname=self._host,
            port=self._port,
            timeout=self._timeout,
        )
        try:
            await smtp.connect()
            await smtp.send_message(build_message(mail))
        except aiosmtplib.SMTPException as exc:
            raise MailSendError(f"smtp delivery failed: {exc}") from exc
        finally:
            smtp.close()
        return SentMail(provider="smtp", message_id=None, thread_id=None)
