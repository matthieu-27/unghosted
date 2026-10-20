"""Contact field rules (us-7 item 1). Pure domain.

A contact is free-form on purpose: only the name is mandatory, because a
listing often gives a company and a role long before a person's address.
Everything optional is normalised to ``None`` when blank, so "empty string"
and "not set" never coexist in the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_NAME_LENGTH = 200
MAX_SHORT_FIELD_LENGTH = 200
MAX_NOTES_LENGTH = 5000

# Same pragmatic address check as the mail schemas: the tracker stores plain
# strings too, so the domain does not promise more than the product enforces.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_SCHEMES = ("http://", "https://")


class ContactValidationError(ValueError):
    """A contact field is missing, too long, or malformed."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class ContactFields:
    """Clean contact values, ready for persistence."""

    name: str
    role: str | None
    organization: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    notes: str | None


def _optional(value: str | None, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_length:
        raise ContactValidationError(
            f"{field} exceeds {max_length} characters", field=field
        )
    return trimmed


def validate_email(value: str | None) -> str | None:
    email = _optional(value, field="email", max_length=MAX_SHORT_FIELD_LENGTH)
    if email is not None and not _EMAIL_PATTERN.match(email):
        raise ContactValidationError(
            f"{email!r} is not an email address", field="email"
        )
    return email


def validate_profile_url(value: str | None) -> str | None:
    url = _optional(value, field="profile_url", max_length=MAX_NOTES_LENGTH)
    if url is not None and not url.lower().startswith(_URL_SCHEMES):
        raise ContactValidationError(
            "profile_url must start with http:// or https://", field="profile_url"
        )
    return url


def validate_contact(
    *,
    name: str,
    role: str | None = None,
    organization: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    profile_url: str | None = None,
    notes: str | None = None,
) -> ContactFields:
    """Validate and normalise one contact. Raises ContactValidationError."""
    clean_name = name.strip()
    if not clean_name:
        raise ContactValidationError("name is required", field="name")
    if len(clean_name) > MAX_NAME_LENGTH:
        raise ContactValidationError(
            f"name exceeds {MAX_NAME_LENGTH} characters", field="name"
        )
    return ContactFields(
        name=clean_name,
        role=_optional(role, field="role", max_length=MAX_SHORT_FIELD_LENGTH),
        organization=_optional(
            organization, field="organization", max_length=MAX_SHORT_FIELD_LENGTH
        ),
        email=validate_email(email),
        phone=_optional(phone, field="phone", max_length=MAX_SHORT_FIELD_LENGTH),
        profile_url=validate_profile_url(profile_url),
        notes=_optional(notes, field="notes", max_length=MAX_NOTES_LENGTH),
    )


def search_pattern(query: str) -> str:
    """SQL ``LIKE`` pattern for a contact search term (us-7 item 1).

    The wildcards a user types stay literal: searching for "50%" must not
    turn into "match anything".
    """
    escaped = (
        query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"
