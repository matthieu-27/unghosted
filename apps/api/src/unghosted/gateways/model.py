"""Model provider gateway (ADR 0008): Mistral hosted, Ollama later.

Logging rule (ADR 0008): task type, provider, token counts, latency —
never prompt or completion content.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from unghosted.domain.link_analysis import PAGE_KINDS

logger = logging.getLogger(__name__)

_MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"


class ModelUnavailableError(RuntimeError):
    """No provider is configured (missing API key) or the call failed."""


@dataclass(frozen=True)
class ExtractionTask:
    """Fill unfilled tracker fields from page text. ``specs`` comes from
    ``domain.link_analysis.model_field_specs``."""

    page_kind: str
    page_text: str
    specs: list[dict[str, Any]]


@dataclass(frozen=True)
class ProfileDraftTask:
    """Draft an applicant profile (us-4 item 3) from the project's
    model-eligible document texts plus its description."""

    project_description: str | None
    document_texts: list[dict[str, str]]
    """``[{"type_key": ..., "text": ...}]`` — eligible documents only
    (ADR 0009), enforced before the gateway is touched."""


PROFILE_FIELDS = ("headline", "seeking", "motivation", "availability")
PROFILE_LIST_FIELDS = ("highlights", "style_notes")


@dataclass(frozen=True)
class LetterDraftTask:
    """Draft a customised letter (us-5 item 2) from the approved profile,
    the row and the listing text, derived from the user's generic
    motivation letter."""

    contact_name: str | None
    company: str | None
    position: str | None
    language: str
    listing_text: str
    profile: dict[str, Any]
    """Approved profile content: text fields plus highlights as
    ``[{"id": ..., "text": ...}]``."""
    motivation_letter_text: str | None


@dataclass(frozen=True)
class FirstContactDraftTask:
    """Draft the first-contact email (us-5 item 3): short when a letter is
    attached, grounded in approved profile highlights."""

    contact_name: str | None
    company: str | None
    position: str | None
    language: str
    listing_text: str
    profile: dict[str, Any]
    letter_attached: bool


class ModelGateway(Protocol):
    provider: str

    async def extract_fields(self, task: ExtractionTask) -> dict[str, Any]:
        """Return ``{column_key: value}`` for the fields it could fill."""
        ...

    async def classify_kind(self, page_text: str) -> str | None:
        """Page kind from PAGE_KINDS, or None when not confident."""
        ...

    async def draft_profile(self, task: ProfileDraftTask) -> dict[str, Any]:
        """Return profile content: text fields from PROFILE_FIELDS and lists
        of plain strings from PROFILE_LIST_FIELDS."""
        ...

    async def draft_letter(self, task: LetterDraftTask) -> dict[str, Any]:
        """Return ``{"text": str, "used_highlights": [ids]}`` — ids of the
        profile highlights the letter relies on."""
        ...

    async def draft_first_contact(self, task: FirstContactDraftTask) -> dict[str, Any]:
        """Return ``{"subject": str, "body": str, "used_highlights": [ids]}``."""
        ...


class MistralGateway:
    """Mistral La Plateforme implementation (ADR 0008 terms)."""

    provider = "mistral"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=60.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def _chat_json(self, *, task: str, system: str, user: str) -> dict[str, Any]:
        """One JSON-mode chat completion. Shared scaffolding for every
        model task: auth, temperature 0, error wrapping, ADR-0008 logging."""
        started = time.monotonic()
        try:
            response = await self._client.post(
                _MISTRAL_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            parsed = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ModelUnavailableError(f"mistral call failed: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ModelUnavailableError("model returned a non-object JSON payload")
        logger.info(
            "model call ok",
            extra={
                "task": task,
                "provider": self.provider,
                "model": self._model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "latency_ms": int((time.monotonic() - started) * 1000),
            },
        )
        return parsed

    async def extract_fields(self, task: ExtractionTask) -> dict[str, Any]:
        system = (
            "You extract structured fields from a web page for a spreadsheet row. "
            "Return a JSON object whose keys are field keys from the list and whose "
            "values are plain values of the declared type. Omit every field you "
            "cannot find or map confidently. Never invent values."
        )
        user = json.dumps(
            {
                "page_kind": task.page_kind,
                "fields": task.specs,
                "page_text": task.page_text[:20_000],
            },
            ensure_ascii=False,
        )
        parsed = await self._chat_json(task="extract_fields", system=system, user=user)
        allowed = {spec["key"] for spec in task.specs}
        return {k: v for k, v in parsed.items() if k in allowed}

    async def classify_kind(self, page_text: str) -> str | None:
        system = (
            "Classify a web page into exactly one kind from this list: "
            + ", ".join(PAGE_KINDS)
            + '. Return a JSON object {"kind": "...", "confident": true|false}. '
            "Use other when nothing fits. Set confident false when unsure."
        )
        parsed = await self._chat_json(
            task="classify_kind", system=system, user=page_text[:20_000]
        )
        kind = parsed.get("kind")
        if (
            not isinstance(kind, str)
            or kind not in PAGE_KINDS
            or not parsed.get("confident")
        ):
            return None
        return kind

    async def draft_profile(self, task: ProfileDraftTask) -> dict[str, Any]:
        system = (
            "You draft an applicant profile from provided documents. "
            "Return a JSON object with keys: headline (one sentence), "
            "seeking (what the applicant is looking for), highlights "
            "(list of short factual sentences), motivation (one paragraph), "
            "style_notes (list of short observations about writing style), "
            "availability (text). Base every statement only on the provided "
            "documents. Never invent facts, never include salary or financial "
            "figures. Omit what you cannot support."
        )
        user = json.dumps(
            {
                "project_description": task.project_description,
                "documents": [
                    {"type_key": d["type_key"], "text": d["text"][:20_000]}
                    for d in task.document_texts
                ],
            },
            ensure_ascii=False,
        )
        parsed = await self._chat_json(task="draft_profile", system=system, user=user)
        result: dict[str, Any] = {
            key: parsed[key]
            for key in PROFILE_FIELDS
            if isinstance(parsed.get(key), str)
        }
        for key in PROFILE_LIST_FIELDS:
            value = parsed.get(key)
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                result[key] = value
        return result

    async def draft_letter(self, task: LetterDraftTask) -> dict[str, Any]:
        system = (
            "You draft a customised application letter from an approved profile. "
            "Write a formal business letter in the requested language, fitting "
            "one A4 page. Derive tone and facts from the provided motivation "
            "letter and profile only; never invent experience, dates or "
            "figures. Greet the contact by name when known. Return a JSON "
            "object with keys: text (the letter body, plain text, no HTML), "
            "used_highlights (ids of profile highlights the letter relies on)."
        )
        user = json.dumps(
            {
                "language": task.language,
                "contact_name": task.contact_name,
                "company": task.company,
                "position": task.position,
                "listing_text": task.listing_text[:20_000],
                "profile": task.profile,
                "motivation_letter": task.motivation_letter_text,
            },
            ensure_ascii=False,
        )
        parsed = await self._chat_json(task="draft_letter", system=system, user=user)
        return {
            "text": parsed.get("text"),
            "used_highlights": parsed.get("used_highlights", []),
        }

    async def draft_first_contact(self, task: FirstContactDraftTask) -> dict[str, Any]:
        system = (
            "You draft a first-contact email for a job application. Write in "
            "the requested language. When a letter is attached, keep it to 3 "
            "to 5 sentences and refer to the attached letter and CV. Base "
            "every statement on the provided profile and listing. No links "
            "except the user's own. Return a JSON object with keys: subject "
            "(short, no placeholders), body (plain text, no HTML), "
            "used_highlights (ids of profile highlights relied on)."
        )
        user = json.dumps(
            {
                "language": task.language,
                "contact_name": task.contact_name,
                "company": task.company,
                "position": task.position,
                "listing_text": task.listing_text[:20_000],
                "profile": task.profile,
                "letter_attached": task.letter_attached,
            },
            ensure_ascii=False,
        )
        parsed = await self._chat_json(
            task="draft_first_contact", system=system, user=user
        )
        return {
            "subject": parsed.get("subject"),
            "body": parsed.get("body"),
            "used_highlights": parsed.get("used_highlights", []),
        }
