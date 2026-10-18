"""Litestar application factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.exceptions import ValidationException
from litestar.middleware import DefineMiddleware

from unghosted.api.auth import JwtAuthMiddleware
from unghosted.api.consents import ConsentController
from unghosted.api.deps import build_dependencies
from unghosted.api.documents import DocumentController
from unghosted.api.error_handlers import validation_exception_handler
from unghosted.api.health import HealthController
from unghosted.api.link_analyses import LinkAnalysisController
from unghosted.api.mail import MailController
from unghosted.api.profiles import ProfileController
from unghosted.api.projects import ProjectController
from unghosted.api.tracker import TrackerController
from unghosted.config import load_settings
from unghosted.db.mongo import create_mongo_client, get_tracker_db
from unghosted.db.sql import create_engine, create_session_factory
from unghosted.domain.documents import parse_master_key
from unghosted.domain.source_detection import load_source_domains
from unghosted.domain.templates import load_templates
from unghosted.gateways.encrypt import EnvelopeEncryptor
from unghosted.gateways.fetch import HttpPageFetcher
from unghosted.gateways.jwks import JwksClient
from unghosted.gateways.mail import SmtpMailGateway
from unghosted.gateways.model import MistralGateway
from unghosted.gateways.pdf import PlaywrightPdfGateway
from unghosted.gateways.storage import LocalStorageGateway, S3StorageGateway
from unghosted.services.link_analysis import TemplateRules, UserRateLimiter

if TYPE_CHECKING:
    from unghosted.config import Settings

MAX_ANALYSES_PER_MINUTE = 10


def create_app(settings: Settings | None = None) -> Litestar:
    """Wire settings, databases, gateways and controllers."""
    settings = settings or load_settings()

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    mongo_client = create_mongo_client(settings)
    mongo_db = get_tracker_db(mongo_client, settings.mongo_database)
    templates = load_templates(settings.shared_templates_dir)

    fetcher = HttpPageFetcher(
        max_bytes=settings.fetch_max_bytes,
        timeout_seconds=settings.fetch_timeout_seconds,
    )
    model_gateway = (
        MistralGateway(api_key=settings.mistral_api_key, model=settings.mistral_model)
        if settings.mistral_api_key
        else None
    )
    source_domains = load_source_domains(
        settings.shared_templates_dir.parent / "source-domains.json"
    )
    template_rules = {
        key: TemplateRules(
            hints=template.analysis_hints,
            allowed_page_kinds=frozenset(template.allowed_page_kinds),
        )
        for key, template in templates.items()
    }

    encryptor = EnvelopeEncryptor(parse_master_key(settings.master_key))
    mail_gateway = SmtpMailGateway(
        host=settings.smtp_host,
        port=settings.smtp_port,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
    pdf_gateway = PlaywrightPdfGateway()
    jwks_client = JwksClient(
        url=settings.auth_jwks_url,
        timeout_seconds=settings.auth_jwks_timeout_seconds,
    )
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise ValueError("storage_backend=s3 requires UNGHOSTED_S3_BUCKET")
        storage: LocalStorageGateway | S3StorageGateway = S3StorageGateway(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
        )
    else:
        storage = LocalStorageGateway(settings.storage_dir)

    async def on_shutdown(app: Litestar) -> None:
        await fetcher.close()
        await jwks_client.close()
        if model_gateway is not None:
            await model_gateway.close()
        if isinstance(storage, S3StorageGateway):
            await storage.close()
        await mongo_client.close()
        await engine.dispose()

    return Litestar(
        path="/api/v1",
        route_handlers=[
            HealthController,
            ProjectController,
            TrackerController,
            LinkAnalysisController,
            DocumentController,
            ProfileController,
            MailController,
            ConsentController,
        ],
        dependencies=build_dependencies(),
        # Liveness and the OpenAPI schema stay public; everything else needs
        # a Better Auth JWT (us-6 item 3).
        middleware=[
            DefineMiddleware(
                JwtAuthMiddleware,
                exclude=["^/api/v1/health", "^/api/v1/schema"],
            )
        ],
        exception_handlers={ValidationException: validation_exception_handler},
        cors_config=CORSConfig(allow_origins=settings.cors_origins)
        if settings.cors_origins
        else None,
        on_shutdown=[on_shutdown],
        state=State(
            {
                "settings": settings,
                "session_factory": session_factory,
                "mongo_client": mongo_client,
                "mongo_db": mongo_db,
                "templates": templates,
                "fetcher": fetcher,
                "model_gateway": model_gateway,
                "rate_limiter": UserRateLimiter(
                    max_calls=MAX_ANALYSES_PER_MINUTE, window_seconds=60.0
                ),
                "source_domains": source_domains,
                "template_rules": template_rules,
                "storage": storage,
                "encryptor": encryptor,
                "mail_gateway": mail_gateway,
                "pdf_gateway": pdf_gateway,
                "jwks_client": jwks_client,
            }
        ),
    )
