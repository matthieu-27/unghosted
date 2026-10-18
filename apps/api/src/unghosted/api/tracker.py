"""Tracker endpoints: fetch and the operations batch."""

from __future__ import annotations

import uuid
from typing import Any

from litestar import Controller, get, patch
from litestar.di import NamedDependency
from litestar.exceptions import (
    HTTPException,
    NotFoundException,
    ValidationException,
)
from litestar.params import FromPath

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.operations import OperationError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.repositories.tracker import StaleRevisionError, TrackerNotFoundError
from unghosted.schemas import (
    ColumnDefinitionModel,
    OperationsBody,
    OperationsResult,
    TrackerDefinitionModel,
    TrackerPayload,
    TrackerRowModel,
)
from unghosted.services.tracker import TrackerService


def _column_model(raw: dict[str, Any]) -> ColumnDefinitionModel:
    # Templates store the key as the label fallback; the model handles the rest.
    raw = {**raw, "label": raw.get("label", raw["key"])}
    return ColumnDefinitionModel.model_validate(raw)


class TrackerController(Controller):
    path = "/projects/{project_id:uuid}/tracker"

    @get()
    async def get_tracker(
        self,
        project_id: FromPath[uuid.UUID],
        tracker_service: NamedDependency[TrackerService],
        current_user: NamedDependency[uuid.UUID],
    ) -> TrackerPayload:
        try:
            state = await tracker_service.fetch(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except TrackerNotFoundError as exc:
            raise NotFoundException(
                detail="tracker not found for this project",
                extra={"code": "not_found"},
            ) from exc
        definition = dict(state.definition)
        definition.pop("_id", None)
        definition.pop("project_id", None)
        return TrackerPayload(
            definition=TrackerDefinitionModel(
                template_key=str(definition["template_key"]),
                template_version=int(definition["template_version"]),
                revision=int(definition["revision"]),
                columns=[_column_model(c) for c in definition["columns"]],
                conditional_rules=list(definition.get("conditional_rules", [])),
                settings=dict(definition.get("settings", {})),
            ),
            rows=[
                TrackerRowModel(
                    id=str(r["_id"]),
                    order_key=str(r["order_key"]),
                    cells=dict(r["cells"]),
                )
                for r in state.rows
            ],
        )

    @patch("/operations", dto=StrictPydanticDTO[OperationsBody])
    async def apply_operations(
        self,
        project_id: FromPath[uuid.UUID],
        data: OperationsBody,
        tracker_service: NamedDependency[TrackerService],
        current_user: NamedDependency[uuid.UUID],
    ) -> OperationsResult:
        try:
            result = await tracker_service.apply(
                project_id,
                current_user,
                base_revision=data.base_revision,
                raw_operations=data.operations,
            )
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except TrackerNotFoundError as exc:
            raise NotFoundException(
                detail="tracker not found for this project",
                extra={"code": "not_found"},
            ) from exc
        except StaleRevisionError as exc:
            raise HTTPException(
                status_code=409,
                detail="tracker moved on: rebase and retry",
                extra={
                    "code": "stale_revision",
                    "current_revision": exc.current_revision,
                },
            ) from exc
        except OperationError as exc:
            raise ValidationException(
                detail=str(exc),
                extra={"code": "validation_failed", "field_errors": exc.field_errors},
            ) from exc
        return OperationsResult(revision=result.revision, applied=result.applied)
