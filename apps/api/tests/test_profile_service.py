"""Profile service: eligibility barrier, consent gate, version flow (us-4
item 3, ADR 0009). The barrier test is the phase acceptance gate: an
ineligible document must never reach the model gateway."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from unghosted.domain.eligibility import IneligibleDocumentError
from unghosted.domain.profiles import ProfileContent
from unghosted.gateways.model import ModelUnavailableError, ProfileDraftTask
from unghosted.services.consents import ConsentRequiredError
from unghosted.services.profiles import (
    NoEligibleDocumentsError,
    ProfileNotEditableError,
    ProfileService,
)

OWNER = uuid.UUID(int=1)
PROJECT_ID = uuid.UUID(int=2)


@dataclass
class FakeProject:
    id: uuid.UUID
    owner: uuid.UUID
    description: str | None = "Apprenticeship in data engineering"


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, FakeProject] = {}

    async def get(self, project_id: uuid.UUID, owner: uuid.UUID) -> FakeProject:
        from unghosted.repositories.projects import ProjectNotFoundError

        project = self.projects.get(project_id)
        if project is None or project.owner != owner:
            raise ProjectNotFoundError(str(project_id))
        return project


@dataclass
class FakeDocument:
    type_key: str
    model_eligible: bool


@dataclass
class FakeDocumentText:
    text: str


class FakeTextRepository:
    """Stands in for list_eligible_for_project's joined rows. The pairs
    below deliberately allow an ineligible row through, because the barrier
    must hold even if the query regresses (ADR 0009 point 3)."""

    def __init__(self, pairs: list[tuple[FakeDocumentText, FakeDocument]]) -> None:
        self.pairs = pairs

    async def list_eligible_for_project(
        self, project_id: uuid.UUID
    ) -> list[tuple[FakeDocumentText, FakeDocument]]:
        return self.pairs


@dataclass
class FakeProfile:
    project_id: uuid.UUID
    version_number: int
    status: str = "draft"
    headline: str | None = None
    seeking: str | None = None
    highlights: list[dict[str, Any]] = field(default_factory=list)
    motivation: str | None = None
    style_notes: list[dict[str, Any]] = field(default_factory=list)
    availability: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, FakeProfile] = {}

    async def list_for_project(self, project_id: uuid.UUID) -> list[FakeProfile]:
        return sorted(
            (r for r in self.rows.values() if r.project_id == project_id),
            key=lambda r: r.version_number,
        )

    async def get(self, project_id: uuid.UUID, version_number: int) -> FakeProfile:
        from unghosted.repositories.profiles import ProfileVersionNotFoundError

        row = self.rows.get(version_number)
        if row is None or row.project_id != project_id:
            raise ProfileVersionNotFoundError(str(version_number))
        return row

    async def next_version_number(self, project_id: uuid.UUID) -> int:
        return max(self.rows, default=0) + 1

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        version_number: int,
        headline: str | None,
        seeking: str | None,
        highlights: list[dict[str, Any]],
        motivation: str | None,
        style_notes: list[dict[str, Any]],
        availability: str | None,
    ) -> FakeProfile:
        row = FakeProfile(
            project_id=project_id,
            version_number=version_number,
            headline=headline,
            seeking=seeking,
            highlights=highlights,
            motivation=motivation,
            style_notes=style_notes,
            availability=availability,
        )
        self.rows[version_number] = row
        return row

    async def update_fields(
        self, profile: FakeProfile, content: ProfileContent
    ) -> FakeProfile:
        for name in (
            "headline",
            "seeking",
            "highlights",
            "motivation",
            "style_notes",
            "availability",
        ):
            value = getattr(content, name)
            if value is not None:
                setattr(profile, name, value)
        profile.updated_at = datetime.now(UTC)
        return profile

    async def approve(self, profile: FakeProfile) -> FakeProfile:
        for row in self.rows.values():
            if row.project_id == profile.project_id and row.status == "approved":
                row.status = "superseded"
        profile.status = "approved"
        profile.approved_at = datetime.now(UTC)
        return profile


class RecordingModel:
    """ModelGateway stand-in that records every task it receives. The
    link-analysis methods exist only to satisfy the Protocol and fail the
    test if anything calls them."""

    provider = "fake"

    def __init__(self, draft: dict[str, Any] | None = None) -> None:
        self.tasks: list[ProfileDraftTask] = []
        self._draft = draft or {
            "headline": "Curious data apprentice",
            "seeking": "A work-study data role",
            "highlights": ["Built a tracker", "Loves clean data"],
            "motivation": "Wants to learn",
            "style_notes": ["Direct tone"],
            "availability": "From September",
        }

    async def draft_profile(self, task: ProfileDraftTask) -> dict[str, Any]:
        self.tasks.append(task)
        return self._draft

    async def extract_fields(self, task: Any) -> dict[str, Any]:
        raise AssertionError("profile tests never extract tracker fields")

    async def classify_kind(self, page_text: str) -> str | None:
        raise AssertionError("profile tests never classify pages")

    async def draft_letter(self, task: Any) -> dict[str, Any]:
        raise AssertionError("profile tests never draft letters")

    async def draft_first_contact(self, task: Any) -> dict[str, Any]:
        raise AssertionError("profile tests never draft first contacts")


class FakeConsentRepository:
    def __init__(self, active: bool) -> None:
        self._active = active

    async def has_active(self, user_id: uuid.UUID, kind: str) -> bool:
        return self._active


def build_service(
    *,
    consent_active: bool = True,
    model: RecordingModel | None = None,
    pairs: list[tuple[FakeDocumentText, FakeDocument]] | None = None,
) -> tuple[ProfileService, RecordingModel | None, FakeProfileRepository]:
    projects = FakeProjectRepository()
    projects.projects[PROJECT_ID] = FakeProject(PROJECT_ID, OWNER)
    profiles = FakeProfileRepository()
    service = ProfileService(
        # Fakes mirror the repository method surface; the real classes are
        # AsyncSession-bound, so the constructor types reject them.
        projects=projects,  # type: ignore[arg-type]
        profiles=profiles,  # type: ignore[arg-type]
        texts=FakeTextRepository(pairs or []),  # type: ignore[arg-type]
        model=model,
        consents=FakeConsentRepository(consent_active),  # type: ignore[arg-type]
    )
    return service, model, profiles


def eligible_pairs() -> list[tuple[FakeDocumentText, FakeDocument]]:
    return [
        (FakeDocumentText("Python, SQL, dashboards"), FakeDocument("cv", True)),
        (
            FakeDocumentText("Motivated by apprenticeships"),
            FakeDocument("motivation_letter", True),
        ),
    ]


async def test_draft_refused_without_model_processing_consent() -> None:
    service, model, _ = build_service(consent_active=False, model=RecordingModel())
    with pytest.raises(ConsentRequiredError, match="draft a profile"):
        await service.draft(PROJECT_ID, OWNER)
    assert model is not None and model.tasks == []


async def test_draft_fails_when_no_model_provider_is_configured() -> None:
    service, _, _ = build_service(model=None, pairs=eligible_pairs())
    with pytest.raises(ModelUnavailableError, match="no model provider"):
        await service.draft(PROJECT_ID, OWNER)


async def test_draft_fails_when_no_eligible_document_text_exists() -> None:
    service, model, _ = build_service(model=RecordingModel(), pairs=[])
    with pytest.raises(NoEligibleDocumentsError, match="upload an eligible document"):
        await service.draft(PROJECT_ID, OWNER)
    assert model is not None and model.tasks == []


async def test_draft_never_sends_an_ineligible_document_to_the_gateway() -> None:
    """ADR 0009 acceptance gate: even if the eligible-texts query regresses
    and returns an ineligible row, the domain barrier refuses before the
    gateway call and the gateway records no task."""
    pairs = eligible_pairs() + [
        (FakeDocumentText("secret id card text"), FakeDocument("id_document", False))
    ]
    service, model, _ = build_service(model=RecordingModel(), pairs=pairs)
    with pytest.raises(IneligibleDocumentError, match="id_document"):
        await service.draft(PROJECT_ID, OWNER)
    assert model is not None and model.tasks == []


async def test_draft_sends_eligible_texts_and_assigns_stable_ids() -> None:
    service, model, _ = build_service(model=RecordingModel(), pairs=eligible_pairs())
    view = await service.draft(PROJECT_ID, OWNER)
    assert model is not None
    assert len(model.tasks) == 1
    task = model.tasks[0]
    assert task.project_description == "Apprenticeship in data engineering"
    assert [d["type_key"] for d in task.document_texts] == ["cv", "motivation_letter"]
    assert view.version == 1
    assert view.status == "draft"
    assert [h["id"] for h in view.highlights] == ["h1", "h2"]
    assert [s["id"] for s in view.style_notes] == ["s1"]
    assert view.headline == "Curious data apprentice"


async def test_regenerating_creates_a_new_draft_and_keeps_the_approved_version() -> (
    None
):
    """Regen never overwrites an approved version (us-4 item 3): the
    approved row keeps its status and content, the new draft lands on the
    next version number."""
    service, _, profiles = build_service(model=RecordingModel(), pairs=eligible_pairs())
    first = await service.draft(PROJECT_ID, OWNER)
    approved = await service.approve(PROJECT_ID, OWNER, first.version)
    assert approved.status == "approved"

    second = await service.draft(PROJECT_ID, OWNER)
    assert second.version == 2
    assert second.status == "draft"
    assert profiles.rows[1].status == "approved"
    assert profiles.rows[1].headline == "Curious data apprentice"


async def test_edit_updates_only_the_fields_the_client_sent() -> None:
    service, _, _ = build_service(model=RecordingModel(), pairs=eligible_pairs())
    draft = await service.draft(PROJECT_ID, OWNER)
    updated = await service.edit(
        PROJECT_ID,
        OWNER,
        draft.version,
        ProfileContent(
            headline="Better headline",
            highlights=[{"id": "h1", "text": "Kept by hand"}],
        ),
    )
    assert updated.headline == "Better headline"
    # Untouched fields keep their drafted values.
    assert updated.seeking == "A work-study data role"
    assert updated.motivation == "Wants to learn"
    assert updated.availability == "From September"
    assert updated.highlights == [{"id": "h1", "text": "Kept by hand"}]


async def test_edit_and_approve_of_an_approved_version_are_refused() -> None:
    service, _, _ = build_service(model=RecordingModel(), pairs=eligible_pairs())
    draft = await service.draft(PROJECT_ID, OWNER)
    await service.approve(PROJECT_ID, OWNER, draft.version)
    with pytest.raises(ProfileNotEditableError, match="only drafts can be edited"):
        await service.edit(
            PROJECT_ID, OWNER, draft.version, ProfileContent(headline="No")
        )
    with pytest.raises(ProfileNotEditableError, match="only drafts can be approved"):
        await service.approve(PROJECT_ID, OWNER, draft.version)


async def test_approving_a_new_draft_supersedes_the_previous_approved_version() -> None:
    service, _, profiles = build_service(model=RecordingModel(), pairs=eligible_pairs())
    first = await service.draft(PROJECT_ID, OWNER)
    await service.approve(PROJECT_ID, OWNER, first.version)
    second = await service.draft(PROJECT_ID, OWNER)
    approved = await service.approve(PROJECT_ID, OWNER, second.version)
    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert profiles.rows[1].status == "superseded"


async def test_state_reports_approved_draft_and_full_history() -> None:
    service, _, _ = build_service(model=RecordingModel(), pairs=eligible_pairs())
    first = await service.draft(PROJECT_ID, OWNER)
    await service.approve(PROJECT_ID, OWNER, first.version)
    second = await service.draft(PROJECT_ID, OWNER)
    assert second.version == 2
    state = await service.state(PROJECT_ID, OWNER)
    assert state.approved is not None
    assert state.approved.version == 1
    assert state.draft is not None
    assert state.draft.version == 2
    assert [v.version for v in state.versions] == [1, 2]
