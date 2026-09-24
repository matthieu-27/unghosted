"""Typed tracker operations: validation and pure application.

The same code path serves the web client and the reply worker (system
author). Operations are the only way tracker state changes.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import Field, TypeAdapter, ValidationError

from unghosted.domain.templates import ColumnDefinition, SelectOption

# Column keys become Mongo document keys: reject reserved characters
# (injection guard, ADR 0001) and keep them readable.
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class OperationError(ValueError):
    """An operation is malformed or does not apply to the current state."""

    def __init__(
        self, message: str, *, field_errors: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.field_errors = field_errors or {}


class CellValidationError(OperationError):
    """A cell value fails the schema built from its column definition."""


# --- operations (discriminated by `op` at the API boundary) ---------------


@dataclass(frozen=True)
class SetCell:
    row_id: str
    column_key: str
    value: Any = None


@dataclass(frozen=True)
class InsertRows:
    after_row_id: str | None
    count: int


@dataclass(frozen=True)
class DeleteRows:
    row_ids: tuple[str, ...]


@dataclass(frozen=True)
class MoveRow:
    row_id: str
    after_row_id: str | None


@dataclass(frozen=True)
class InsertColumn:
    after_column_key: str | None
    column: dict[str, Any]


@dataclass(frozen=True)
class UpdateColumn:
    column_key: str
    column: dict[str, Any]


@dataclass(frozen=True)
class DeleteColumn:
    column_key: str


@dataclass(frozen=True)
class MoveColumn:
    column_key: str
    after_column_key: str | None


@dataclass(frozen=True)
class ResizeColumn:
    column_key: str
    width: int


Operation = (
    SetCell
    | InsertRows
    | DeleteRows
    | MoveRow
    | InsertColumn
    | UpdateColumn
    | DeleteColumn
    | MoveColumn
    | ResizeColumn
)


def op_from_dict(raw: dict[str, Any]) -> Operation:
    """Parse one operation payload. Raises OperationError on bad shape."""
    kind = raw.get("op")
    try:
        if kind == "set_cell":
            return SetCell(
                row_id=str(raw["row_id"]),
                column_key=str(raw["column_key"]),
                value=raw.get("value"),
            )
        if kind == "insert_rows":
            count = int(raw["count"])
            if count < 1 or count > 100:
                raise OperationError("insert_rows count must be between 1 and 100")
            after = raw.get("after_row_id")
            return InsertRows(
                after_row_id=str(after) if after is not None else None, count=count
            )
        if kind == "delete_rows":
            ids = tuple(str(i) for i in raw["row_ids"])
            if not ids:
                raise OperationError("delete_rows requires at least one row_id")
            return DeleteRows(row_ids=ids)
        if kind == "move_row":
            after = raw.get("after_row_id")
            return MoveRow(
                row_id=str(raw["row_id"]),
                after_row_id=str(after) if after is not None else None,
            )
        if kind == "insert_column":
            column = validated_column(raw["column"])
            after = raw.get("after_column_key")
            return InsertColumn(
                after_column_key=str(after) if after is not None else None,
                column=column,
            )
        if kind == "update_column":
            column = validated_column(raw["column"], allow_key=raw["column_key"])
            return UpdateColumn(column_key=str(raw["column_key"]), column=column)
        if kind == "delete_column":
            return DeleteColumn(column_key=str(raw["column_key"]))
        if kind == "move_column":
            after = raw.get("after_column_key")
            return MoveColumn(
                column_key=str(raw["column_key"]),
                after_column_key=str(after) if after is not None else None,
            )
        if kind == "resize_column":
            width = int(raw["width"])
            if width < 40 or width > 2000:
                raise OperationError("column width must be between 40 and 2000")
            return ResizeColumn(column_key=str(raw["column_key"]), width=width)
    except KeyError as exc:
        raise OperationError(f"{kind} is missing field {exc}") from exc
    except (TypeError, ValueError) as exc:
        if isinstance(exc, OperationError):
            raise
        raise OperationError(f"{kind} has an invalid field: {exc}") from exc
    raise OperationError(f"unknown operation {kind!r}")


# --- column validation ----------------------------------------------------

_ALLOWED_COLUMN_TYPES = {
    "text",
    "long-text",
    "number",
    "currency",
    "percent",
    "date",
    "select",
    "checkbox",
    "url",
    "email",
    "phone",
    "rating",
    "contact-link",
    "document-link",
    "computed",
}


def validated_column(
    raw: dict[str, Any], *, allow_key: str | None = None
) -> dict[str, Any]:
    """Shape-check a column definition coming from insert/update_column."""
    key = str(raw.get("key", ""))
    if not _KEY_PATTERN.match(key) or key.startswith("$") or "." in key:
        raise OperationError(f"invalid column key {key!r}")
    if allow_key is not None and key != str(allow_key):
        raise OperationError(
            "update_column cannot rename a column: key must match column_key"
        )
    column_type = str(raw.get("type", ""))
    if column_type not in _ALLOWED_COLUMN_TYPES:
        raise OperationError(f"invalid column type {column_type!r}")
    result: dict[str, Any] = {
        "key": key,
        "type": column_type,
        "label": str(raw.get("label", key)),
        "system": False,
    }
    if column_type == "select":
        options = raw.get("options")
        if not isinstance(options, list) or not options:
            raise OperationError("select columns require a non-empty options list")
        result["options"] = [
            {"key": str(o["key"]), "label": str(o.get("label", o["key"]))}
            for o in options
        ]
    return result


# --- cell validation (dynamic pydantic schema per column) ----------------


def _cell_adapter(column: ColumnDefinition) -> TypeAdapter[Any]:
    """Build the dynamic validation schema for one column (brief 4.3:
    schemas generated from the column definitions — pydantic, per owner
    decision 2026-09-21)."""
    column_type = column.type
    if column_type in {"text", "long-text", "url", "email", "phone"}:
        return TypeAdapter(str | None)
    if column_type in {"number", "currency", "percent"}:
        return TypeAdapter(Annotated[float | None, Field(allow_inf_nan=False)])
    if column_type == "rating":
        top = column.max or 5
        return TypeAdapter(
            Annotated[float | None, Field(ge=0, le=top, allow_inf_nan=False)],
        )
    if column_type == "date":
        return TypeAdapter(Annotated[str | None, Field(pattern=_DATE_PATTERN.pattern)])
    if column_type == "select":
        keys = [o.key for o in column.options or ()]
        choices = "|".join(re.escape(k) for k in keys)
        return TypeAdapter(Annotated[str | None, Field(pattern=f"^({choices})$")])
    if column_type == "checkbox":
        return TypeAdapter(bool | None)
    if column_type in {"contact-link", "document-link"}:
        return TypeAdapter(list[uuid.UUID] | None)
    raise OperationError(
        f"column {column.key!r} of type {column_type!r} holds no editable value",
    )


def validate_cell(
    columns: dict[str, ColumnDefinition],
    column_key: str,
    value: Any,
    *,
    system_allowed: bool = False,
) -> Any:
    """Validate a cell value against the dynamic schema. Returns the clean value."""
    column = columns.get(column_key)
    if column is None:
        raise CellValidationError(f"unknown column {column_key!r}")
    if column.system and not system_allowed:
        raise CellValidationError(
            f"column {column_key!r} is system-managed: written only by the reply worker",
        )
    if column.computed:
        raise CellValidationError(f"column {column_key!r} is computed: read-only")
    try:
        return _cell_adapter(column).validate_python(value)
    except ValidationError as exc:
        joined = {
            str(err["loc"][0]) if err["loc"] else "value": err["msg"]
            for err in exc.errors()
        }
        raise CellValidationError(
            f"invalid value for column {column_key!r}",
            field_errors=joined,
        ) from exc


# --- fractional order keys -------------------------------------------------

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_BASE = len(_ALPHABET)
_SEED_KEY = "a" * 8


def key_between(before: str | None, after: str | None) -> str:
    """A string sorting strictly between ``before`` and ``after`` (either may
    be None, meaning the open end). A move rewrites only the moved row's key.

    Keys are fractional-index strings: plain lexicographic order equals
    numeric order over the digit strings with implicit trailing zeros —
    appending digits moves a key toward 1, so extensions always sort after
    their prefix. Midpoints are computed as big-int averages at the smallest
    width that leaves room, then trailing zeros are stripped (they carry no
    fractional value).
    """
    if before is None and after is None:
        return _SEED_KEY
    if before is not None and after is not None and not before < after:
        raise OperationError("order keys: before must sort lower than after")
    if before is None:
        assert after is not None
        return _fractional_midpoint("0" * 8, after)
    if after is None:
        # Any extension of a key sorts right after it: append the mid digit.
        return before + _ALPHABET[_BASE // 2]
    return _fractional_midpoint(before, after)


def _digits(key: str, width: int) -> int:
    """Value of the key zero-extended to `width` digits (trailing zeros)."""
    padded = key + "0" * (width - len(key))
    return _key_to_int(padded)


def _key_to_int(key: str) -> int:
    total = 0
    for ch in key:
        total = total * _BASE + _ALPHABET.index(ch)
    return total


def _int_to_key(value: int) -> str:
    digits: list[str] = []
    while value > 0:
        value, rest = divmod(value, _BASE)
        digits.append(_ALPHABET[rest])
    return "".join(reversed(digits)) or "0"


def _fractional_midpoint(a: str, b: str) -> str:
    """A key strictly between a and b (a < b in lex order)."""
    width = max(len(a), len(b)) + 1
    while True:
        va, vb = _digits(a, width), _digits(b, width)
        mid = (va + vb) // 2
        if va < mid < vb:
            return _int_to_key(mid).rstrip("0") or "0"
        width += 1


def new_row_id() -> str:
    return str(uuid.uuid4())


# --- pure application ------------------------------------------------------


@dataclass(frozen=True)
class AppliedBatch:
    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    upserted_row_ids: tuple[str, ...]
    changed_row_ids: tuple[str, ...]
    deleted_row_ids: tuple[str, ...]


def column_defs(columns: list[dict[str, Any]]) -> dict[str, ColumnDefinition]:
    result: dict[str, ColumnDefinition] = {}
    for raw in columns:
        options = None
        if "options" in raw:
            options = tuple(
                SelectOption(o["key"], o["label"], o.get("color"))
                for o in raw["options"]
            )
        result[raw["key"]] = ColumnDefinition(
            key=raw["key"],
            type=raw["type"],
            label=raw.get("label", raw["key"]),
            options=options,
            system=bool(raw.get("system", False)),
            currency=raw.get("currency"),
            max=raw.get("max"),
            computed=raw.get("computed"),
        )
    return result


def apply_operations(
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    operations: list[Operation],
) -> AppliedBatch:
    """Apply a batch purely: no IO, no mutation of the inputs.

    Rows are dictionaries ``{_id, order_key, cells}`` in current order.
    """
    columns = [dict(c) for c in columns]
    rows = sorted(({**r} for r in rows), key=lambda r: r["order_key"])
    upserted: list[str] = []
    changed: list[str] = []
    deleted: list[str] = []

    def row_by_id(row_id: str) -> dict[str, Any]:
        for row in rows:
            if str(row["_id"]) == row_id:
                return row
        raise OperationError(f"unknown row {row_id!r}")

    for operation in operations:
        if isinstance(operation, SetCell):
            row = row_by_id(operation.row_id)
            clean = validate_cell(
                column_defs(columns), operation.column_key, operation.value
            )
            if clean is None:
                row["cells"].pop(operation.column_key, None)
            else:
                row["cells"][operation.column_key] = clean
            if str(row["_id"]) not in changed:
                changed.append(str(row["_id"]))

        elif isinstance(operation, InsertRows):
            for _ in range(operation.count):
                if operation.after_row_id is not None:
                    anchor = row_by_id(operation.after_row_id)
                    idx = rows.index(anchor)
                    before = rows[idx]["order_key"]
                    after = rows[idx + 1]["order_key"] if idx + 1 < len(rows) else None
                else:
                    before = rows[-1]["order_key"] if rows else None
                    after = None
                fresh: dict[str, Any] = {
                    "_id": new_row_id(),
                    "order_key": key_between(before, after),
                    "cells": {},
                }
                position = (
                    rows.index(row_by_id(operation.after_row_id)) + 1
                    if operation.after_row_id
                    else len(rows)
                )
                rows.insert(position, fresh)
                upserted.append(fresh["_id"])

        elif isinstance(operation, DeleteRows):
            for row_id in operation.row_ids:
                row_by_id(row_id)  # fail whole batch if any id is unknown
            keep = [r for r in rows if str(r["_id"]) not in set(operation.row_ids)]
            deleted.extend(operation.row_ids)
            rows = keep

        elif isinstance(operation, MoveRow):
            moved = row_by_id(operation.row_id)
            rest = [r for r in rows if r is not moved]
            if operation.after_row_id is None:
                before = rest[-1]["order_key"] if rest else None
                after = None
            else:
                anchor = row_by_id(operation.after_row_id)
                idx = rest.index(anchor)
                before = rest[idx]["order_key"]
                after = rest[idx + 1]["order_key"] if idx + 1 < len(rest) else None
            moved["order_key"] = key_between(before, after)
            upserted.append(str(moved["_id"]))

        elif isinstance(operation, InsertColumn):
            keys = {c["key"] for c in columns}
            if operation.column["key"] in keys:
                raise OperationError(
                    f"column {operation.column['key']!r} already exists"
                )
            fresh = dict(operation.column)
            position = len(columns)
            if operation.after_column_key is not None:
                position = next(
                    (
                        i + 1
                        for i, c in enumerate(columns)
                        if c["key"] == operation.after_column_key
                    ),
                    len(columns),
                )
            columns.insert(position, fresh)

        elif isinstance(operation, UpdateColumn):
            for i, c in enumerate(columns):
                if c["key"] == operation.column_key:
                    if c.get("system"):
                        raise OperationError(
                            f"column {operation.column_key!r} is system-managed: read-only"
                        )
                    columns[i] = dict(operation.column)
                    break
            else:
                raise OperationError(f"unknown column {operation.column_key!r}")

        elif isinstance(operation, DeleteColumn):
            target = next(
                (c for c in columns if c["key"] == operation.column_key), None
            )
            if target is None:
                raise OperationError(f"unknown column {operation.column_key!r}")
            if target.get("system"):
                raise OperationError(
                    f"column {operation.column_key!r} is system-managed: cannot delete"
                )
            columns = [c for c in columns if c["key"] != operation.column_key]
            for row in rows:
                row["cells"].pop(operation.column_key, None)
                if str(row["_id"]) not in changed:
                    changed.append(str(row["_id"]))

        elif isinstance(operation, MoveColumn):
            existing_keys = [c["key"] for c in columns]
            if operation.column_key not in existing_keys:
                raise OperationError(f"unknown column {operation.column_key!r}")
            moved = next(c for c in columns if c["key"] == operation.column_key)
            rest = [c for c in columns if c["key"] != operation.column_key]
            if operation.after_column_key is None:
                rest.append(moved)
            else:
                idx = next(
                    (
                        i
                        for i, c in enumerate(rest)
                        if c["key"] == operation.after_column_key
                    ),
                    len(rest) - 1,
                )
                rest.insert(idx + 1, moved)
            columns = rest

        elif isinstance(operation, ResizeColumn):
            for c in columns:
                if c["key"] == operation.column_key:
                    c["width"] = operation.width
                    break
            else:
                raise OperationError(f"unknown column {operation.column_key!r}")

    return AppliedBatch(
        columns=columns,
        rows=rows,
        upserted_row_ids=tuple(upserted),
        changed_row_ids=tuple(changed),
        deleted_row_ids=tuple(deleted),
    )
