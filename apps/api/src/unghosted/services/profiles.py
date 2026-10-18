"""Applicant-profile service: draft, edit, approve (us-4 item 3).

The model reads eligible document texts plus the project description only
(ADR 0009). Regenerating creates a new draft version; an approved version
is never modified by the service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from unghosted.domain.eligibility import DocumentRef, ensure_model_eligible
from unghosted.domain.profiles import ProfileContent
from unghosted.gateways.model import ModelUnavailableError, ProfileDraftTask
from unghosted.services.consents import require_model_consent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unghosted.db.models import ApplicantProfile
    from unghosted.gateways.model import ModelGateway
    from unghosted.repositories.consents import ConsentRepository
    from unghosted.repositories.documents import DocumentTextRepository
    from unghosted.repositories.profiles import ApplicantProfileRepository
    from unghosted.repositories.projects import ProjectRepository


class NoEligibleDocumentsError(ValueError):
    """No model-eligible document text exists for this project: nothing to
    ground a profile on, and inventing one is out of the question."""


class ProfileNotEditableError(RuntimeError):
    """Only draft versions can be edited or approved (us-4 item 3)."""


@dataclass(frozen=True)
class ProfileVersionView:
    version: int
    status: str
    headline: str | None
    seeking: str | None
    highlights: list[dict[str, Any]]
    motivation: str | None
    style_notes: list[dict[str, Any]]
    availability: str | None
    approved_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProfileState:
    approved: ProfileVersionView | None
    draft: ProfileVersionView | None
    versions: list[ProfileVersionView]


def _version_view(profile: ApplicantProfile) -> ProfileVersionView:
    return ProfileVersionView(
        version=profile.version_number,
        status=profile.status,
        headline=profile.headline,
        seeking=profile.seeking,
        highlights=list(profile.highlights),
        motivation=profile.motivation,
        style_notes=list(profile.style_notes),
        availability=profile.availability,
        approved_at=profile.approved_at.isoformat()
        if profile.approved_at is not None
        else None,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


def _with_ids(items: list[str], prefix: str) -> list[dict[str, Any]]:
    """Server-assigned stable ids (us-4 item 3): the model returns plain
    strings, the service owns the ids the UI edits against."""
    return [
        {"id": f"{prefix}{index}", "text": text}
        for index, text in enumerate(items, start=1)
    ]


class ProfileService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        profiles: ApplicantProfileRepository,
        texts: DocumentTextRepository,
        model: ModelGateway | None,
        consents: ConsentRepository,
    ) -> None:
        self._projects = projects
        self._profiles = profiles
        self._texts = texts
        self._model = model
        self._consents = consents

    async def state(self, project_id: uuid.UUID, owner: uuid.UUID) -> ProfileState:
        project = await self._projects.get(project_id, owner)
        rows: Sequence[ApplicantProfile] = await self._profiles.list_for_project(
            project.id
        )
        views = [_version_view(p) for p in rows]
        approved = next((v for v in views if v.status == "approved"), None)
        draft = next((v for v in views if v.status == "draft"), None)
        return ProfileState(approved=approved, draft=draft, versions=views)

    async def draft(
        self, project_id: uuid.UUID, owner: uuid.UUID
    ) -> ProfileVersionView:
        project = await self._projects.get(project_id, owner)
        await require_model_consent(self._consents, owner, "draft a profile")
        pairs = await self._texts.list_eligible_for_project(project.id)
        if not pairs:
            # Checked before provider availability: "upload a document" is
            # actionable, "model unavailable" is not.
            raise NoEligibleDocumentsError(
                "upload an eligible document first (ADR 0009)"
            )
        if self._model is None:
            raise ModelUnavailableError(
                "no model provider is configured (missing API key)"
            )
        # ADR 0009 point 3: the domain layer rejects ineligible inputs before
        # the gateway is touched. The query filters by the snapshot flag; this
        # check re-reads the flag from the joined rows, so a query regression
        # fails here instead of at the provider.
        refs = [
            DocumentRef(
                type_key=document.type_key, model_eligible=document.model_eligible
            )
            for _, document in pairs
        ]
        ensure_model_eligible(refs)

        task = ProfileDraftTask(
            project_description=project.description,
            document_texts=[
                {"type_key": document.type_key, "text": text.text}
                for text, document in pairs
            ],
        )
        raw = await self._model.draft_profile(task)
        draft = await self._profiles.create(
            project_id=project.id,
            version_number=await self._profiles.next_version_number(project.id),
            headline=raw.get("headline"),
            seeking=raw.get("seeking"),
            highlights=_with_ids(raw.get("highlights", []), "h"),
            motivation=raw.get("motivation"),
            style_notes=_with_ids(raw.get("style_notes", []), "s"),
            availability=raw.get("availability"),
        )
        return _version_view(draft)

    async def edit(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        version: int,
        content: ProfileContent,
    ) -> ProfileVersionView:
        profile = await self._editable_draft(project_id, owner, version, "edited")
        return _version_view(await self._profiles.update_fields(profile, content))

    async def approve(
        self, project_id: uuid.UUID, owner: uuid.UUID, version: int
    ) -> ProfileVersionView:
        profile = await self._editable_draft(project_id, owner, version, "approved")
        return _version_view(await self._profiles.approve(profile))

    async def _editable_draft(
        self, project_id: uuid.UUID, owner: uuid.UUID, version: int, verb: str
    ) -> ApplicantProfile:
        await self._projects.get(project_id, owner)
        profile = await self._profiles.get(project_id, version)
        if profile.status != "draft":
            raise ProfileNotEditableError(
                f"version {version} is {profile.status}, only drafts can be {verb}"
            )
        return profile
