"""Link analysis: input detection, page kind, structured extraction.

Pure and deterministic-first (us-3 items 1, 3, 4): JSON-LD before
OpenGraph before URL patterns, model only for gaps (in the service, via
the model gateway). Provenance is attached to every field.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

PAGE_KINDS = (
    "job_offer",
    "company",
    "careers",
    "school_program",
    "housing_listing",
    "agency",
    "other",
)

Provenance = str
"""One of: structured, meta, model, detection, manual."""

_SCRIPT_JSONLD = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_META_OG = re.compile(
    r'<meta[^>]+property=["\']og:([a-zA-Z0-9:_-]+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_OG_REVERSED = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:([a-zA-Z0-9:_-]+)["\']',
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

_URL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (kind, fragments matched against lowercased path + host)
    (
        "housing_listing",
        ("/annonce", "/location", "/appartement", "/rent", "/louer", "leboncoin"),
    ),
    (
        "job_offer",
        ("/job", "/offre-emploi", "/offre_emploi", "/vacancy", "/poste", "/mission"),
    ),
    ("careers", ("/careers", "/carriere", "/jobs", "/recrutement")),
    ("agency", ("/agence", "/agency", "/cabinet")),
    ("school_program", ("/programme", "/formation", "/apprentissage", "/alternance")),
)


class InputNotProvidedError(ValueError):
    """Empty paste."""


@dataclass(frozen=True)
class KindVerdict:
    kind: str
    confidence: str  # high | medium | low
    basis: str  # jsonld | open_graph | url_pattern


@dataclass(frozen=True)
class ExtractedField:
    column_key: str
    value: Any
    provenance: Provenance


def detect_input(raw: str) -> str:
    """``url`` when the paste is one http(s) URL, ``text`` otherwise."""
    stripped = raw.strip()
    if not stripped:
        raise InputNotProvidedError("nothing to analyze")
    if not _WS.search(stripped):
        split = urlsplit(stripped)
        if split.scheme in {"http", "https"} and split.hostname:
            return "url"
    return "text"


def clean_html(html: str, *, limit: int = 20_000) -> str:
    """Readable text from HTML: tags stripped, whitespace collapsed,
    truncated. No JS is ever fetched or executed (us-3 item 2)."""
    headless = re.sub(
        r"<(script|style|noscript|svg|head)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = _TAG.sub(" ", headless)
    text = text.replace("&amp;", "&").replace("&nbsp;", " ")
    text = text.replace("&eacute;", "é").replace("&egrave;", "è")
    return _WS.sub(" ", text).strip()[:limit]


def detect_page_kind(html: str, url: str) -> KindVerdict | None:
    """Deterministic page-kind detection, strongest signal first."""
    for entry in _jsonld_objects(html):
        kinds = entry.get("@type")
        if isinstance(kinds, str):
            kinds = [kinds]
        if not isinstance(kinds, list):
            continue
        if any(str(k).lower() == "jobposting" for k in kinds):
            return KindVerdict("job_offer", "high", "jsonld")
    og = _open_graph(html)
    og_type = str(og.get("type", "")).lower()
    path = urlsplit(url).path.lower()
    if og_type in {"product", "article"} and any(
        fragment in path for fragment in ("/rent", "/location", "/annonce")
    ):
        return KindVerdict("housing_listing", "medium", "open_graph")
    haystack = url.lower()
    for kind, fragments in _URL_PATTERNS:
        if any(fragment in haystack for fragment in fragments):
            return KindVerdict(kind, "low", "url_pattern")
    return None


def extract_structured(
    html: str,
    url: str,
    hint_keys: list[str],
) -> list[ExtractedField]:
    """Structured-data extraction, limited to the template's hint columns."""
    fields: list[ExtractedField] = []
    taken: set[str] = set()

    def offer(key: str, value: Any, provenance: Provenance) -> None:
        if value in (None, "", []) or key in taken or key not in hint_keys:
            return
        taken.add(key)
        fields.append(ExtractedField(key, value, provenance))

    for entry in _jsonld_objects(html):
        kinds = entry.get("@type")
        if isinstance(kinds, str):
            kinds = [kinds]
        if not isinstance(kinds, list) or not any(
            str(k).lower() == "jobposting" for k in kinds
        ):
            continue
        offer("position", entry.get("title"), "structured")
        organization = entry.get("hiringOrganization") or {}
        if isinstance(organization, dict):
            offer("company", organization.get("name"), "structured")
        location = _first_location(entry.get("jobLocation"))
        offer("location", location, "structured")
        offer(
            "salary_range_advertised",
            _salary_text(entry.get("baseSalary")),
            "structured",
        )
        offer("listing_url", url, "detection")
        break

    if "listing_url" not in taken and "listing_url" in hint_keys:
        offer("listing_url", url, "detection")

    og = _open_graph(html)
    offer("position", og.get("title"), "meta")
    if "notes" in hint_keys:
        summary = clean_html(html, limit=280)
        offer("notes", summary or None, "detection")
    return fields


def model_field_specs(
    columns: list[dict[str, Any]],
    hint_keys: list[str],
    filled_keys: set[str],
) -> list[dict[str, Any]]:
    """Field descriptions for the model prompt: unfilled hint columns with
    their type and options, so the model returns valid values or nothing."""
    specs: list[dict[str, Any]] = []
    for raw in columns:
        if raw["key"] in filled_keys or raw["key"] not in hint_keys:
            continue
        if raw.get("system") or raw.get("computed"):
            continue
        if raw["type"] in {"contact-link", "document-link"}:
            continue
        spec: dict[str, Any] = {
            "key": raw["key"],
            "type": raw["type"],
            "label": raw.get("label", raw["key"]),
        }
        if raw["type"] == "select" and isinstance(raw.get("options"), list):
            spec["options"] = [o["key"] for o in raw["options"]]
        specs.append(spec)
    return specs


# --- internals --------------------------------------------------------------


def _jsonld_objects(html: str) -> list[dict[str, Any]]:
    """Parsed JSON-LD objects, tolerating malformed blocks (@graph walked)."""
    objects: list[dict[str, Any]] = []
    for match in _SCRIPT_JSONLD.finditer(html):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        stack = [parsed]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                objects.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
            elif isinstance(item, list):
                stack.extend(item)
    return objects


def _open_graph(html: str) -> dict[str, str]:
    og: dict[str, str] = {}
    for name, content in _META_OG.findall(html):
        og[name] = content
    for content, name in _META_OG_REVERSED.findall(html):
        og.setdefault(name, content)
    return og


def _first_location(raw: Any) -> str | None:
    if not isinstance(raw, list):
        raw = [raw] if raw else []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        address = entry.get("address")
        if isinstance(address, dict):
            parts = [
                address.get(k)
                for k in ("addressLocality", "addressRegion", "postalCode")
            ]
            joined = " ".join(str(p) for p in parts if p)
            if joined:
                return joined
    return None


def _salary_text(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    currency = raw.get("currency") or raw.get("code")
    if isinstance(value, dict):
        amount = value.get("value")
        unit = value.get("unitText")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            text = f"{amount:g} {currency or ''}".strip()
            if unit:
                text += f" ({unit})"
            return text
    return None
