"""Link-analysis endpoint: POST /projects/{id}/link-analyses (us-3)."""

from __future__ import annotations

import uuid

from litestar import Controller, post
from litestar.di import NamedDependency
from litestar.exceptions import HTTPException, NotFoundException, ValidationException
from litestar.params import FromPath
from litestar.status_codes import HTTP_429_TOO_MANY_REQUESTS

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.link_analysis import InputNotProvidedError
from unghosted.domain.ssrf import FetchBlockedError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import (
    AnalysisWarningModel,
    ExtractedFieldModel,
    LinkAnalysisBody,
    LinkAnalysisResult,
)
from unghosted.services.link_analysis import LinkAnalysisService, RateLimitedError


class LinkAnalysisController(Controller):
    path = "/projects/{project_id:uuid}/link-analyses"

    @post(status_code=200, dto=StrictPydanticDTO[LinkAnalysisBody])
    async def analyze(
        self,
        project_id: FromPath[uuid.UUID],
        data: LinkAnalysisBody,
        link_analysis_service: NamedDependency[LinkAnalysisService],
        current_user: NamedDependency[uuid.UUID],
    ) -> LinkAnalysisResult:
        try:
            outcome = await link_analysis_service.analyze(
                project_id,
                current_user,
                data.input,
                force_kind=data.force_kind,
            )
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except InputNotProvidedError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "validation_failed"}
            ) from exc
        except FetchBlockedError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "fetch_blocked"}
            ) from exc
        except RateLimitedError as exc:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
                extra={"code": "rate_limited"},
            ) from exc
        return LinkAnalysisResult(
            page_kind=outcome.page_kind,
            page_kind_confidence=outcome.page_kind_confidence,
            page_kind_basis=outcome.page_kind_basis,
            provider=outcome.provider,
            cached=outcome.cached,
            fields=[
                ExtractedFieldModel(
                    column_key=f.column_key, value=f.value, provenance=f.provenance
                )
                for f in outcome.fields
            ],
            warnings=[
                AnalysisWarningModel(code=w.code, detail=w.detail)
                for w in outcome.warnings
            ],
        )
