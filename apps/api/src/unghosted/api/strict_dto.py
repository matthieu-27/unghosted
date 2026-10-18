"""Request-body DTO that keeps pydantic strictness on the wire.

The default PydanticDTO decodes bytes through a msgspec transfer model with
``strict=False`` (litestar/dto/_backend.py ``parse_raw``), so ``"2"`` becomes
``2`` before the pydantic model ever runs and ``model_config strict=True``
never applies. This DTO validates the raw payload with the model itself.
"""

from __future__ import annotations

from typing import Any, TypeVar

from litestar.exceptions import ValidationException
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StrictPydanticDTO(PydanticDTO[T]):
    """Decode bodies via ``model_validate``, preserving strict semantics."""

    def decode_builtins(self, value: dict[str, Any]) -> Any:
        try:
            return self.model_type.model_validate(value)
        except ValidationError as ex:
            raise ValidationException(extra=_error_list(ex)) from ex

    def decode_bytes(self, value: bytes) -> Any:
        try:
            return self.model_type.model_validate_json(value)
        except ValidationError as ex:
            raise ValidationException(extra=_error_list(ex)) from ex


def _error_list(exc: ValidationError) -> list[dict[str, Any]]:
    """HTTP-contract error entries: location, message, input kind (no values)."""
    return [
        {
            "loc": list(err["loc"]),
            "msg": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
