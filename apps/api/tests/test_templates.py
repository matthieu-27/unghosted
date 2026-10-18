"""Template loading and tracker instantiation (pure domain)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unghosted.domain.templates import (
    ColumnDefinition,
    TemplateError,
    instantiate_tracker,
    load_templates,
)

SHARED = Path(__file__).resolve().parents[3] / "packages" / "shared" / "templates"


def test_load_real_templates_finds_both() -> None:
    templates = load_templates(SHARED)
    assert set(templates) == {"apprenticeship-search", "rental-search"}


def test_columns_match_design_column_count() -> None:
    templates = load_templates(SHARED)
    assert len(templates["apprenticeship-search"].columns) == 23
    assert len(templates["rental-search"].columns) == 14


def test_system_columns_flagged() -> None:
    templates = load_templates(SHARED)
    apprentice = templates["apprenticeship-search"]
    assert {c.key for c in apprentice.columns if c.system} == {
        "response_date",
        "reply_type",
    }


def test_instantiate_merges_defaults_and_values() -> None:
    template = load_templates(SHARED)["apprenticeship-search"]
    definition = instantiate_tracker(template, {"contract_end_date": "2027-08-31"})
    settings: dict[str, object] = definition["settings"]
    assert settings["contract_end_date"] == "2027-08-31"
    assert settings["no_response_threshold_days"] == 21
    assert definition["revision"] == 0
    assert definition["columns"][0]["key"] == "date_sent"


def test_instantiate_rejects_unknown_setting() -> None:
    template = load_templates(SHARED)["rental-search"]
    with pytest.raises(TemplateError, match="unknown setting"):
        instantiate_tracker(template, {"max_budget": 100})


def test_instantiate_rejects_wrong_type() -> None:
    template = load_templates(SHARED)["rental-search"]
    with pytest.raises(TemplateError, match="expects number"):
        instantiate_tracker(template, {"max_budget_rent": "cheap"})


def test_missing_directory_raises() -> None:
    with pytest.raises(TemplateError, match="not found"):
        load_templates(Path("does/not/exist"))


def test_column_lookup() -> None:
    template = load_templates(SHARED)["apprenticeship-search"]
    column: ColumnDefinition | None = template.column("status")
    assert column is not None
    assert column.type == "select"
    assert column.options is not None
    assert len(column.options) == 13
