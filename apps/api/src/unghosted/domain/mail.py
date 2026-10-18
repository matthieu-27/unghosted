"""Sending rules and draft grounding checks (us-5 items 3 and 5).

Limits are domain-layer decisions, not gateway checks: the same rule must
hold for SMTP (M4), Gmail and Graph (post-MVP). Grounding checks produce
warnings the editor shows — the user's explicit edit or send click is the
confirmation that model output is applied (us-5 item 5 of the brief).
"""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

DraftKind = Literal["customised_letter", "first_contact_email"]
"""The two draft kinds (us-5 items 2 and 3) — plain str on the wire."""

DraftStatus = Literal["draft", "approved", "sent", "discarded"]

LETTER_KIND: DraftKind = "customised_letter"
FIRST_CONTACT_KIND: DraftKind = "first_contact_email"
DRAFT_STATUS: DraftStatus = "draft"

MAX_MAIL_ATTACHMENT_BYTES = 25 * 1024 * 1024
"""Total attachment cap per email. Gmail's limit; SMTP/Mailpit accepts more
but the same rule must hold for every provider (us-5 item 4)."""

FIRST_CONTACT_SENTENCE_RANGE = (3, 5)
"""Short first-contact emails when a letter is attached (us-5 item 3)."""

RECIPIENT_COOLDOWN = timedelta(days=7)
"""Minimum between two emails to the same recipient (us-5 item 5)."""

_PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}]*\}\}|<<[^<>]*>>")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

# Small stopword probes: enough to catch a language switch between the
# listing and the drafted email, without a dependency.
_FRENCH_WORDS = frozenset(
    [
        "le",
        "la",
        "les",
        "un",
        "une",
        "du",
        "de",
        "des",
        "je",
        "tu",
        "il",
        "elle",
        "nous",
        "vous",
        "ils",
        "elles",
        "et",
        "à",
        "au",
        "aux",
        "ce",
        "cet",
        "cette",
        "pour",
        "avec",
        "dans",
        "sur",
        "pas",
        "plus",
        "votre",
        "mon",
        "notre",
        "suis",
        "êtes",
    ]
)
_ENGLISH_WORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "to",
        "and",
        "you",
        "i",
        "we",
        "they",
        "he",
        "she",
        "it",
        "is",
        "are",
        "for",
        "with",
        "on",
        "in",
        "this",
        "that",
        "your",
        "our",
        "my",
        "am",
        "was",
        "were",
        "be",
    ]
)


class SendLimitError(ValueError):
    """The send would break a domain sending rule.

    The message is user-facing; ``code`` is the stable wire value.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_UTC = ZoneInfo("UTC")


def day_start(now: datetime, zone: ZoneInfo) -> datetime:
    """UTC instant of the local calendar-day start in ``zone``.

    The daily cap counts sends per project-local day (us-5 item 5), so the
    boundary must move with the zone, not the server clock.
    """
    local = now.astimezone(zone)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(_UTC)


def assert_send_allowed(
    *,
    sent_today: int,
    daily_cap: int,
    recipient_last_sent: datetime | None,
    now: datetime,
) -> None:
    """Raise SendLimitError when the send must not happen.

    ``sent_today`` counts this project's outbound messages since the local
    day start (see day_start). ``recipient_last_sent`` is the most recent
    send to this recipient on this project, whatever the mailbox. Exactly
    RECIPIENT_COOLDOWN elapsed is allowed: the rule is a minimum spacing,
    not a strict inequality.
    """
    if sent_today >= daily_cap:
        raise SendLimitError(
            "daily_cap_reached",
            f"project reached its daily cap of {daily_cap} first-contact emails",
        )
    if (
        recipient_last_sent is not None
        and now - recipient_last_sent < RECIPIENT_COOLDOWN
    ):
        raise SendLimitError(
            "recipient_cooldown",
            f"last email to this recipient was less than {RECIPIENT_COOLDOWN.days} "
            "days ago",
        )


def detect_language(text: str) -> str | None:
    """'fr' or 'en' by stopword hit count, None when nothing matches."""
    words = re.findall(r"[a-zàâçéèêëîïôùûü]+", text.lower())
    french = sum(word in _FRENCH_WORDS for word in words)
    english = sum(word in _ENGLISH_WORDS for word in words)
    if french == english == 0:
        return None
    return "fr" if french > english else "en"


@dataclass(frozen=True)
class GroundingWarning:
    """One grounding issue the editor must surface (us-5 item 3)."""

    code: str
    message: str


def validate_grounding(
    *,
    text: str,
    used_highlights: list[str],
    known_highlight_ids: list[str],
    company: str | None,
    contact_name: str | None,
    expected_language: str | None,
    own_links: list[str],
    letter_attached: bool,
) -> list[GroundingWarning]:
    """Check a drafted email against the facts it claims to rely on.

    Warnings never block: the user edits or sends anyway (explicit click,
    us-5 item 5). The server recomputes them so the UI cannot hide them.
    """
    warnings: list[GroundingWarning] = []
    known = set(known_highlight_ids)
    unknown = [highlight for highlight in used_highlights if highlight not in known]
    if unknown:
        warnings.append(
            GroundingWarning(
                code="unknown_highlight",
                message=f"the email cites profile facts that no longer exist: "
                f"{', '.join(unknown)}",
            )
        )
    if _PLACEHOLDER_PATTERN.search(text):
        warnings.append(
            GroundingWarning(
                code="placeholder_leftover",
                message="the text still contains unfilled placeholders",
            )
        )
    if company and company.lower() not in text.lower():
        warnings.append(
            GroundingWarning(
                code="company_missing",
                message=f"the email does not name the company “{company}”",
            )
        )
    if contact_name and contact_name.lower() not in text.lower():
        warnings.append(
            GroundingWarning(
                code="contact_missing",
                message=f"the email does not greet “{contact_name}”",
            )
        )
    if expected_language is not None:
        actual = detect_language(text)
        if actual is not None and actual != expected_language:
            warnings.append(
                GroundingWarning(
                    code="language_mismatch",
                    message=f"the listing is {expected_language} but the email "
                    f"looks {actual}",
                )
            )
    allowed = {link.rstrip("/") for link in own_links}
    for url in _URL_PATTERN.findall(text):
        if url.rstrip("/") not in allowed:
            warnings.append(
                GroundingWarning(
                    code="foreign_link",
                    message=f"the email links to {url}, which is not one of your own",
                )
            )
    if letter_attached:
        sentences = len([part for part in re.split(r"[.!?]+", text) if part.strip()])
        low, high = FIRST_CONTACT_SENTENCE_RANGE
        if not low <= sentences <= high:
            warnings.append(
                GroundingWarning(
                    code="length_out_of_range",
                    message=f"a first contact with a letter attached should be "
                    f"{low}–{high} sentences, this one has {sentences}",
                )
            )
    return warnings


def own_links_from_text(*texts: str | None) -> list[str]:
    """Links the user provided themselves (profile, documents): allowed in
    a drafted email (us-5 item 3 — “no links except the user's own”)."""
    links: list[str] = []
    for text in texts:
        if text:
            links.extend(_URL_PATTERN.findall(text))
    return links


def attachment_document_ids(attachments: list[uuid.UUID]) -> list[uuid.UUID]:
    """Dedupe while keeping order — a document attached twice is sent once."""
    seen: list[uuid.UUID] = []
    for document_id in attachments:
        if document_id not in seen:
            seen.append(document_id)
    return seen


def today_value(now: datetime, zone: ZoneInfo) -> str:
    """The row-cell form of “today” for date columns (ISO local date)."""
    return now.astimezone(zone).date().isoformat()


def days_since(sent: date, now: date) -> int:
    """Computed-column helper: calendar days between two local dates."""
    return (now - sent).days


def letter_html(
    body_text: str,
    *,
    contact_name: str | None,
    company: str | None,
    date_text: str,
) -> str:
    """French business-letter layout (us-5 item 2) for the PDF gateway.

    The model owns the words; this owns the page. The body is escaped and
    rendered verbatim — model output is never interpreted as HTML.
    """
    recipient_lines = [line for line in (contact_name, company) if line]
    recipient_html = "".join(
        f"<div>{html.escape(line)}</div>" for line in recipient_lines
    )
    paragraphs = "".join(
        f"<p>{html.escape(paragraph).replace('\n', '<br>')}</p>"
        for block in body_text.strip().split("\n\n")
        if (paragraph := block.strip())
    )
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        "<style>"
        "body{font-family:'Times New Roman',serif;font-size:12pt;"
        "line-height:1.6;color:#000;margin:0}"
        ".date{text-align:right}.recipient{margin-bottom:2em}"
        "p{margin:0 0 1em 0;text-align:justify}"
        "</style></head><body>"
        f'<div class="date">{html.escape(date_text)}</div>'
        f'<div class="recipient">{recipient_html}</div>'
        f"{paragraphs}"
        "</body></html>"
    )
