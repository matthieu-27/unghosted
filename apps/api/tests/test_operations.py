"""Operations: parsing, cell validation, order keys, pure application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from unghosted.domain.operations import (
    CellValidationError,
    OperationError,
    apply_operations,
    key_between,
    op_from_dict,
    validate_cell,
)
from unghosted.domain.templates import load_templates

SHARED = Path(__file__).resolve().parents[3] / "packages" / "shared" / "templates"
TEMPLATES = load_templates(SHARED)


def _columns() -> dict[str, Any]:
    template = TEMPLATES["apprenticeship-search"]
    return {c.key: c for c in template.columns}


def test_parse_set_cell() -> None:
    op = op_from_dict(
        {"op": "set_cell", "row_id": "r1", "column_key": "company", "value": "Acme"}
    )
    assert op is not None


def test_parse_unknown_op_rejected() -> None:
    with pytest.raises(OperationError, match="unknown operation"):
        op_from_dict({"op": "nuke_all"})


def test_parse_insert_rows_bounds() -> None:
    with pytest.raises(OperationError, match="between 1 and 100"):
        op_from_dict({"op": "insert_rows", "count": 0})


def test_cell_select_must_be_known_option() -> None:
    with pytest.raises(CellValidationError):
        validate_cell(_columns(), "status", "dreaming")


def test_cell_select_accepts_known_option() -> None:
    assert validate_cell(_columns(), "status", "hr_interview") == "hr_interview"


def test_cell_date_format_enforced() -> None:
    with pytest.raises(CellValidationError):
        validate_cell(_columns(), "date_sent", "21/09/2026")
    assert validate_cell(_columns(), "date_sent", "2026-09-21") == "2026-09-21"


def test_cell_rating_bounds() -> None:
    with pytest.raises(CellValidationError):
        validate_cell(_columns(), "interest", 6)
    assert validate_cell(_columns(), "interest", 4) == 4


def test_system_column_rejects_user_write() -> None:
    with pytest.raises(CellValidationError, match="system-managed"):
        validate_cell(_columns(), "response_date", "2026-09-21")
    # The reply worker passes with system authority (story 10, item 3).
    assert validate_cell(_columns(), "response_date", "2026-09-21", system_allowed=True)


def test_computed_column_read_only() -> None:
    with pytest.raises(CellValidationError, match="computed"):
        validate_cell(_columns(), "days_since_sent", 3)


def test_unknown_column_rejected() -> None:
    with pytest.raises(CellValidationError, match="unknown column"):
        validate_cell(_columns(), "nope", "x")


def test_column_key_injection_guard() -> None:
    with pytest.raises(OperationError, match="invalid column key"):
        op_from_dict(
            {
                "op": "insert_column",
                "column": {"key": "$where", "type": "text"},
            },
        )
    with pytest.raises(OperationError, match="invalid column key"):
        op_from_dict(
            {
                "op": "insert_column",
                "column": {"key": "a.b", "type": "text"},
            },
        )


def test_key_between_open_ends() -> None:
    assert key_between(None, None)
    first = key_between(None, "bbbb")
    assert first < "bbbb"
    last = key_between("bbbb", None)
    assert last > "bbbb"


def test_key_between_strictly_between() -> None:
    for _ in range(200):
        mid = key_between("aaaa", "bbbb")
        assert "aaaa" < mid < "bbbb"


def test_key_between_exhaustion_widens() -> None:
    # Adjacent keys have no integer midpoint: the key widens instead.
    widened = key_between("a", "b")
    assert "a" < widened < "b"


def test_key_between_monotonic_under_repeated_inserts() -> None:
    keys: list[str] = []
    after: str | None = None
    for _ in range(50):
        nxt = key_between(after, None) if keys else key_between(None, None)
        keys.append(nxt)
        after = nxt
    assert keys == sorted(keys)


def _rows(count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    after: str | None = None
    for _ in range(count):
        key = key_between(after, None)
        rows.append({"_id": f"row-{len(rows)}", "order_key": key, "cells": {}})
        after = key
    return rows


def _definition_columns() -> list[dict[str, Any]]:
    template = TEMPLATES["rental-search"]
    from unghosted.domain.templates import instantiate_tracker

    definition = instantiate_tracker(template, {})
    return list(definition["columns"])


def test_apply_set_cell_and_fetch_roundtrip() -> None:
    rows = _rows(2)
    ops = [
        op_from_dict(
            {
                "op": "set_cell",
                "row_id": "row-0",
                "column_key": "property",
                "value": "2-room 45 m2",
            }
        )
    ]
    batch = apply_operations(_definition_columns(), rows, ops)
    assert batch.rows[0]["cells"]["property"] == "2-room 45 m2"


def test_apply_set_cell_none_clears() -> None:
    rows = _rows(1)
    set_op = op_from_dict(
        {"op": "set_cell", "row_id": "row-0", "column_key": "property", "value": "x"}
    )
    clear_op = op_from_dict(
        {"op": "set_cell", "row_id": "row-0", "column_key": "property", "value": None}
    )
    batch = apply_operations(_definition_columns(), rows, [set_op, clear_op])
    assert "property" not in batch.rows[0]["cells"]


def test_apply_insert_rows_between_keeps_order() -> None:
    rows = _rows(3)
    op = op_from_dict({"op": "insert_rows", "after_row_id": "row-0", "count": 1})
    batch = apply_operations(_definition_columns(), rows, [op])
    assert len(batch.rows) == 4
    order = [r["order_key"] for r in batch.rows]
    assert order == sorted(order)
    assert len(batch.upserted_row_ids) == 1


def test_apply_delete_rows_unknown_id_fails_batch() -> None:
    rows = _rows(1)
    op = op_from_dict({"op": "delete_rows", "row_ids": ["row-0", "ghost"]})
    with pytest.raises(OperationError, match="unknown row"):
        apply_operations(_definition_columns(), rows, [op])


def test_apply_move_row_to_end() -> None:
    rows = _rows(3)
    op = op_from_dict({"op": "move_row", "row_id": "row-0", "after_row_id": "row-2"})
    batch = apply_operations(_definition_columns(), rows, [op])
    ordered = sorted(batch.rows, key=lambda r: r["order_key"])
    assert [str(r["_id"]) for r in ordered][-1] == "row-0"


def test_apply_insert_and_delete_column() -> None:
    rows = _rows(1)
    insert = op_from_dict(
        {
            "op": "insert_column",
            "column": {"key": "priority", "type": "text", "label": "Priority"},
        },
    )
    set_op = op_from_dict(
        {"op": "set_cell", "row_id": "row-0", "column_key": "priority", "value": "high"}
    )
    delete = op_from_dict({"op": "delete_column", "column_key": "priority"})
    batch = apply_operations(_definition_columns(), rows, [insert, set_op, delete])
    assert all(c["key"] != "priority" for c in batch.columns)
    assert "priority" not in batch.rows[0]["cells"]


def test_apply_cannot_delete_system_column() -> None:
    rows = _rows(1)
    op = op_from_dict({"op": "delete_column", "column_key": "response_date"})
    with pytest.raises(OperationError, match="system-managed"):
        apply_operations(_definition_columns(), rows, [op])


def test_apply_resize_and_move_column() -> None:
    rows = _rows(1)
    resize = op_from_dict({"op": "resize_column", "column_key": "notes", "width": 320})
    move = op_from_dict(
        {"op": "move_column", "column_key": "notes", "after_column_key": None}
    )
    batch = apply_operations(_definition_columns(), rows, [resize, move])
    assert batch.columns[-1]["key"] == "notes"
    assert batch.columns[-1]["width"] == 320
