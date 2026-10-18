"""Link-analysis service: the "+ New application" flow (user story 3).

Deterministic before model (product rule): input detection, fetch, page
kind and structured extraction are deterministic. The model gateway only
fills gaps and only when configured. Nothing here writes tracker rows —
the review form saves through the operations path after user confirmation.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from unghosted.db.models import LinkAnalysis
from unghosted.domain.link_analysis import (
    ExtractedField,
    clean_html,
    detect_input,
    detect_page_kind,
    extract_structured,
    model_field_specs,
)
from unghosted.domain.operations import (
    CellValidationError,
    column_defs,
    validate_cell,
)
from unghosted.domain.source_detection import detect_source
from unghosted.gateways.model import ExtractionTask, ModelUnavailableError
from unghosted.repositories.link_analyses import LinkAnalysisRepository
from unghosted.repositories.projects import ProjectRepository
from unghosted.repositories.tracker import TrackerRepository

if TYPE_CHECKING:
    from unghosted.gateways.fetch import PageFetcher
    from unghosted.gateways.model import ModelGateway

CACHE_WINDOW = timedelta(hours=24)
"""Per-URL extraction cache lifetime (eco-design: no repeat fetch)."""


class RateLimitedError(Exception):
    """Too many link analyses from this user (us-3 item 2)."""


class UserRateLimiter:
    """In-memory sliding window. Single-process MVP scale (approved default)."""

    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._calls: dict[uuid.UUID, deque[float]] = defaultdict(deque)

    def check(self, user: uuid.UUID) -> None:
        now = time.monotonic()
        calls = self._calls[user]
        while calls and now - calls[0] > self._window:
            calls.popleft()
        if len(calls) >= self._max:
            raise RateLimitedError(
                f"link analysis rate limit: {self._max} per {self._window:g}s"
            )
        calls.append(now)


@dataclass(frozen=True)
class TemplateRules:
    """Per-template knowledge for analysis, loaded from the shared JSONs.

    Bundled so the service takes one parameter instead of parallel dicts
    (they must never drift apart)."""

    hints: dict[str, list[str]]
    allowed_page_kinds: frozenset[str]
    """Empty = every page kind fits (no mismatch warning)."""


@dataclass(frozen=True)
class AnalysisWarning:
    code: str
    detail: str


@dataclass(frozen=True)
class AnalysisOutcome:
    page_kind: str | None
    page_kind_confidence: str | None
    page_kind_basis: str | None
    provider: str | None
    cached: bool
    fields: list[ExtractedField]
    warnings: list[AnalysisWarning]


class LinkAnalysisService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        tracker: TrackerRepository,
        analyses: LinkAnalysisRepository,
        fetcher: PageFetcher,
        model: ModelGateway | None,
        rate_limiter: UserRateLimiter,
        source_domains: dict[str, str],
        template_rules: dict[str, TemplateRules],
    ) -> None:
        self._projects = projects
        self._tracker = tracker
        self._analyses = analyses
        self._fetcher = fetcher
        self._model = model
        self._rate_limiter = rate_limiter
        self._source_domains = source_domains
        self._template_rules = template_rules

    async def analyze(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        raw_input: str,
        *,
        force_kind: str | None = None,
    ) -> AnalysisOutcome:
        # Ownership gate: raises ProjectNotFoundError for other users' projects.
        await self._projects.get(project_id, owner)
        self._rate_limiter.check(owner)
        input_type = detect_input(raw_input)

        definition = await self._tracker.get_definition(project_id)
        columns: list[dict[str, Any]] = list(definition["columns"])
        template_key = str(definition["template_key"])
        rules = self._template_rules.get(
            template_key, TemplateRules(hints={}, allowed_page_kinds=frozenset())
        )

        if input_type == "url":
            url = raw_input.strip()
            if force_kind is None:
                cached = await self._analyses.cached_for_source(
                    project_id, url, max_age=CACHE_WINDOW
                )
                if cached is not None and cached.raw_output.get("fields") is not None:
                    return _outcome_from_cache(cached)
            return await self._analyze_url(
                project_id, owner, url, columns, rules, force_kind
            )
        return await self._analyze_text(
            project_id, owner, raw_input, columns, rules, force_kind
        )

    # --- url path -------------------------------------------------------------

    async def _analyze_url(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        url: str,
        columns: list[dict[str, Any]],
        rules: TemplateRules,
        force_kind: str | None,
    ) -> AnalysisOutcome:
        hints = _hints(columns, rules, force_kind)
        page = await self._fetcher.fetch(url)
        cleaned = clean_html(page.text)
        kind, confidence, basis, provider = await self._resolve_kind(
            page.text, url, cleaned, force_kind
        )
        if kind is None:
            kind, confidence, basis = "other", "none", "fallback"
        fields = _with_source(
            extract_structured(page.text, url, hints), url, hints, self._source_domains
        )
        fields, provider = await _fill_gaps(
            self._model, kind, cleaned, columns, hints, fields, provider
        )
        warnings = await self._url_warnings(
            project_id, url, kind, rules.allowed_page_kinds
        )

        await self._analyses.create(
            LinkAnalysis(
                project_id=project_id,
                requested_by=owner,
                input_type="url",
                source=url,
                page_kind=kind,
                status="ok",
                provider=provider,
                timings_ms={"fetch_ms": page.elapsed_ms},
                cleaned_text=cleaned,
                raw_output={
                    "kind_basis": basis,
                    "fields": _fields_as_dicts(fields),
                    "final_url": page.final_url,
                },
            )
        )
        return AnalysisOutcome(
            page_kind=kind,
            page_kind_confidence=confidence,
            page_kind_basis=basis,
            provider=provider,
            cached=False,
            fields=fields,
            warnings=warnings,
        )

    # --- text path ------------------------------------------------------------

    async def _analyze_text(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        text: str,
        columns: list[dict[str, Any]],
        rules: TemplateRules,
        force_kind: str | None,
    ) -> AnalysisOutcome:
        cleaned = text.strip()[:20_000]
        kind, confidence, basis, provider = await self._resolve_kind(
            "", "", cleaned, force_kind
        )
        fields: list[ExtractedField] = []
        if kind is not None:
            hints = _hints(columns, rules, kind)
            fields, provider = await _fill_gaps(
                self._model, kind, cleaned, columns, hints, fields, provider
            )
        warnings = _mismatch_warnings(kind, rules.allowed_page_kinds)

        await self._analyses.create(
            LinkAnalysis(
                project_id=project_id,
                requested_by=owner,
                input_type="text",
                source=text[:500],
                page_kind=kind,
                status="ok",
                provider=provider,
                timings_ms={},
                cleaned_text=cleaned,
                raw_output={
                    "kind_basis": basis or "none",
                    "fields": _fields_as_dicts(fields),
                },
            )
        )
        return AnalysisOutcome(
            page_kind=kind,
            page_kind_confidence=confidence,
            page_kind_basis=basis,
            provider=provider,
            cached=False,
            fields=fields,
            warnings=warnings,
        )

    # --- helpers --------------------------------------------------------------

    async def _resolve_kind(
        self,
        html: str,
        url: str,
        cleaned: str,
        force_kind: str | None,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Kind + confidence + basis + provider. Deterministic first, model
        only when inconclusive (us-3 item 3)."""
        if force_kind is not None:
            return force_kind, "forced", "user", None
        if html:
            verdict = detect_page_kind(html, url)
            if verdict is not None:
                return verdict.kind, verdict.confidence, verdict.basis, None
        if self._model is not None:
            kind = await _classify_with_model(self._model, cleaned)
            if kind is not None:
                return kind, "model", "model", self._model.provider
        return None, None, None, None

    async def _url_warnings(
        self,
        project_id: uuid.UUID,
        url: str,
        kind: str,
        allowed_page_kinds: frozenset[str],
    ) -> list[AnalysisWarning]:
        warnings = _mismatch_warnings(kind, allowed_page_kinds)
        if await self._tracker.cell_value_exists(project_id, "listing_url", url):
            warnings.insert(
                0, AnalysisWarning("duplicate_url", "a row already lists this URL")
            )
        return warnings


def _hints(
    columns: list[dict[str, Any]], rules: TemplateRules, kind: str | None
) -> list[str]:
    keys = rules.hints.get(kind or "other") or rules.hints.get("other") or []
    known = {c["key"] for c in columns}
    return [k for k in keys if k in known]


def _with_source(
    fields: list[ExtractedField],
    url: str,
    hints: list[str],
    source_domains: dict[str, str],
) -> list[ExtractedField]:
    if "source" not in hints or any(f.column_key == "source" for f in fields):
        return fields
    source = detect_source(url, source_domains)
    return fields + [ExtractedField("source", source, "detection")]


async def _fill_gaps(
    model: ModelGateway | None,
    kind: str,
    cleaned: str,
    columns: list[dict[str, Any]],
    hints: list[str],
    fields: list[ExtractedField],
    provider: str | None,
) -> tuple[list[ExtractedField], str | None]:
    """Model fills unfilled hint columns. Invalid output is dropped, not
    fatal (us-3 item 4). Returns fields + the effective provider."""
    if model is None or kind is None:
        return fields, provider
    specs = model_field_specs(columns, hints, {f.column_key for f in fields})
    if not specs:
        return fields, provider
    try:
        raw = await model.extract_fields(
            ExtractionTask(page_kind=kind, page_text=cleaned, specs=specs)
        )
    except ModelUnavailableError:
        return fields, provider
    column_defs_map = column_defs(columns)
    filled = list(fields)
    taken = {f.column_key for f in filled}
    for key, value in raw.items():
        if key in taken or value in (None, ""):
            continue
        try:
            clean = validate_cell(column_defs_map, key, value)
        except CellValidationError:
            continue  # invalid model output is dropped, not fatal (us-3 item 4)
        if clean is not None:
            filled.append(ExtractedField(key, clean, "model"))
    return filled, model.provider


async def _classify_with_model(model: ModelGateway, cleaned: str) -> str | None:
    try:
        return await model.classify_kind(cleaned)
    except ModelUnavailableError:
        return None


def _mismatch_warnings(
    kind: str | None, allowed_page_kinds: frozenset[str]
) -> list[AnalysisWarning]:
    if not allowed_page_kinds or kind is None or kind in allowed_page_kinds:
        return []
    return [
        AnalysisWarning(
            "kind_template_mismatch",
            f"page kind {kind} does not fit this project's template",
        )
    ]


def _fields_as_dicts(fields: list[ExtractedField]) -> list[dict[str, Any]]:
    return [
        {"column_key": f.column_key, "value": f.value, "provenance": f.provenance}
        for f in fields
    ]


def _outcome_from_cache(cached: LinkAnalysis) -> AnalysisOutcome:
    raw_fields = cached.raw_output.get("fields")
    if not isinstance(raw_fields, list):
        raw_fields = []
    fields = [
        ExtractedField(str(f["column_key"]), f["value"], str(f["provenance"]))
        for f in raw_fields
        if isinstance(f, dict) and "column_key" in f
    ]
    return AnalysisOutcome(
        page_kind=cached.page_kind,
        page_kind_confidence="cached",
        page_kind_basis="cache",
        provider=cached.provider,
        cached=True,
        fields=fields,
        warnings=[],
    )
