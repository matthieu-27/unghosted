"""API error-shape handlers (contract: docs/api-contract.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.exceptions import ValidationException
from litestar.response import Response

if TYPE_CHECKING:
    from typing import Any

    from litestar.connection import Request


# Sync on purpose: Litestar invokes exception handlers without awaiting.
def validation_exception_handler(
    request: Request[Any, Any, Any],  # unused: required handler signature
    exc: ValidationException,
) -> Response[dict[str, object]]:
    """Litestar defaults validation errors to 400. The API contract pins
    them to 422 and keeps the `extra` payload (error codes, field errors)."""
    return Response(
        content={
            "status_code": 422,
            "detail": exc.detail,
            "extra": exc.extra,
        },
        status_code=422,
    )
