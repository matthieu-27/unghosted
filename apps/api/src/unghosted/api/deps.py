"""Litestar dependencies: db session, mongo, current user, services.

Litestar resolves dependency signatures via `get_type_hints` at startup, so
these imports must exist at runtime — no TYPE_CHECKING here.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from zoneinfo import ZoneInfo

from litestar.connection import Request
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.api.auth import AuthenticatedUser
from unghosted.config import Settings
from unghosted.domain.templates import Template
from unghosted.repositories.consents import ConsentRepository
from unghosted.repositories.documents import (
    DocumentRepository,
    DocumentTextRepository,
)
from unghosted.repositories.link_analyses import LinkAnalysisRepository
from unghosted.repositories.mail import (
    AuditEventRepository,
    EmailContentRepository,
    EmailMessageRepository,
    EmailThreadRepository,
    MailDraftRepository,
)
from unghosted.repositories.profiles import ApplicantProfileRepository
from unghosted.repositories.projects import ProjectRepository
from unghosted.repositories.tracker import TrackerRepository
from unghosted.services.consents import ConsentService
from unghosted.services.documents import DocumentService
from unghosted.services.link_analysis import LinkAnalysisService
from unghosted.services.mail import MailService
from unghosted.services.profiles import ProfileService
from unghosted.services.projects import ProjectService
from unghosted.services.tracker import TrackerService


async def provide_session(state: State) -> AsyncGenerator[AsyncSession]:
    factory = state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def provide_current_user(
    request: Request[AuthenticatedUser, dict[str, object], State],
) -> uuid.UUID:
    """The owner identity `JwtAuthMiddleware` put on the connection."""
    return request.user.user_id


def provide_project_service(
    session: NamedDependency[AsyncSession],
    state: State,
    current_user: NamedDependency[uuid.UUID],
) -> ProjectService:
    templates: dict[str, Template] = state.templates
    return ProjectService(
        ProjectRepository(session),
        TrackerRepository(state.mongo_db),
        templates,
    )


def provide_tracker_service(
    session: NamedDependency[AsyncSession], state: State
) -> TrackerService:
    db: AsyncDatabase[dict[str, object]] = state.mongo_db
    return TrackerService(ProjectRepository(session), TrackerRepository(db))


def provide_link_analysis_service(
    session: NamedDependency[AsyncSession], state: State
) -> LinkAnalysisService:
    db: AsyncDatabase[dict[str, object]] = state.mongo_db
    return LinkAnalysisService(
        projects=ProjectRepository(session),
        tracker=TrackerRepository(db),
        analyses=LinkAnalysisRepository(session),
        fetcher=state.fetcher,
        model=state.model_gateway,
        rate_limiter=state.rate_limiter,
        source_domains=state.source_domains,
        template_rules=state.template_rules,
    )


def provide_document_service(
    session: NamedDependency[AsyncSession],
    state: State,
) -> DocumentService:
    templates: dict[str, Template] = state.templates
    return DocumentService(
        projects=ProjectRepository(session),
        documents=DocumentRepository(session),
        texts=DocumentTextRepository(session),
        storage=state.storage,
        encryptor=state.encryptor,
        consents=ConsentRepository(session),
        templates=templates,
    )


def provide_profile_service(
    session: NamedDependency[AsyncSession],
    state: State,
) -> ProfileService:
    return ProfileService(
        projects=ProjectRepository(session),
        profiles=ApplicantProfileRepository(session),
        texts=DocumentTextRepository(session),
        model=state.model_gateway,
        consents=ConsentRepository(session),
    )


def provide_consent_service(
    session: NamedDependency[AsyncSession],
) -> ConsentService:
    return ConsentService(ConsentRepository(session))


def provide_mail_service(
    session: NamedDependency[AsyncSession],
    state: State,
) -> MailService:
    settings: Settings = state.settings
    db: AsyncDatabase[dict[str, object]] = state.mongo_db
    return MailService(
        projects=ProjectRepository(session),
        tracker=TrackerService(ProjectRepository(session), TrackerRepository(db)),
        analyses=LinkAnalysisRepository(session),
        documents=DocumentRepository(session),
        texts=DocumentTextRepository(session),
        drafts=MailDraftRepository(session),
        threads=EmailThreadRepository(session),
        messages=EmailMessageRepository(session),
        audit=AuditEventRepository(session),
        contents=EmailContentRepository(db),
        profiles=ApplicantProfileRepository(session),
        consents=ConsentRepository(session),
        storage=state.storage,
        encryptor=state.encryptor,
        model=state.model_gateway,
        mail=state.mail_gateway,
        pdf=state.pdf_gateway,
        templates=state.templates,
        mail_from=settings.mail_from,
        daily_send_cap=settings.daily_send_cap,
        zone=ZoneInfo(settings.send_timezone),
    )


def build_dependencies() -> dict[str, Provide]:
    return {
        "session": Provide(provide_session),
        "current_user": Provide(provide_current_user, sync_to_thread=False),
        "project_service": Provide(provide_project_service, sync_to_thread=False),
        "tracker_service": Provide(provide_tracker_service, sync_to_thread=False),
        "link_analysis_service": Provide(
            provide_link_analysis_service, sync_to_thread=False
        ),
        "document_service": Provide(provide_document_service, sync_to_thread=False),
        "profile_service": Provide(provide_profile_service, sync_to_thread=False),
        "consent_service": Provide(provide_consent_service, sync_to_thread=False),
        "mail_service": Provide(provide_mail_service, sync_to_thread=False),
    }
