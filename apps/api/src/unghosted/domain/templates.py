"""Template loading and tracker-definition instantiation. Pure domain."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TemplateError(ValueError):
    """A template file is missing, malformed, or fails validation."""


@dataclass(frozen=True)
class SelectOption:
    key: str
    label: str
    color: str | None = None


@dataclass(frozen=True)
class ColumnDefinition:
    key: str
    type: str
    label: str
    options: tuple[SelectOption, ...] | None = None
    system: bool = False
    currency: str | None = None
    max: int | None = None
    computed: str | None = None


@dataclass(frozen=True)
class DocumentType:
    key: str
    label: str
    model_eligible: bool


@dataclass(frozen=True)
class Template:
    key: str
    version: int
    label: str
    description: str
    settings_schema: dict[str, Any]
    settings_defaults: dict[str, Any]
    columns: tuple[ColumnDefinition, ...]
    document_types: tuple[DocumentType, ...]
    analysis_hints: dict[str, list[str]]
    allowed_page_kinds: tuple[str, ...] = ()
    """Page kinds that fit this template (mismatch warning otherwise).
    Empty means every kind is accepted."""

    def column(self, key: str) -> ColumnDefinition | None:
        return next((c for c in self.columns if c.key == key), None)


def load_templates(directory: Path) -> dict[str, Template]:
    """Load every ``*.json`` template in the directory, keyed by template key."""
    if not directory.is_dir():
        raise TemplateError(f"template directory not found: {directory}")
    templates: dict[str, Template] = {}
    for path in sorted(directory.glob("*.json")):
        template = _parse_template(path)
        if template.key in templates:
            raise TemplateError(f"duplicate template key {template.key!r} in {path}")
        templates[template.key] = template
    if not templates:
        raise TemplateError(f"no templates found in {directory}")
    return templates


def _parse_template(path: Path) -> Template:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateError(f"cannot read template {path}: {exc}") from exc
    try:
        columns = tuple(_parse_column(c, path) for c in raw["columns"])
        document_types = tuple(
            DocumentType(
                key=d["key"], label=d["label"], model_eligible=bool(d["model_eligible"])
            )
            for d in raw["document_types"]
        )
    except (KeyError, TypeError) as exc:
        raise TemplateError(f"malformed template {path}: missing {exc}") from exc
    _check_unique_keys(columns, path)
    return Template(
        key=str(raw["key"]),
        version=int(raw["version"]),
        label=str(raw["label"]),
        description=str(raw.get("description", "")),
        settings_schema=dict(raw.get("settings", {}).get("schema", {})),
        settings_defaults=dict(raw.get("settings", {}).get("defaults", {})),
        columns=columns,
        document_types=document_types,
        analysis_hints={
            str(kind): [str(k) for k in keys]
            for kind, keys in raw.get("analysis_hints", {}).items()
        },
        allowed_page_kinds=tuple(str(k) for k in raw.get("allowed_page_kinds", [])),
    )


def _parse_column(raw: dict[str, Any], path: Path) -> ColumnDefinition:
    try:
        options = None
        if "options" in raw:
            options = tuple(
                SelectOption(
                    key=str(o["key"]), label=str(o["label"]), color=o.get("color")
                )
                for o in raw["options"]
            )
        return ColumnDefinition(
            key=str(raw["key"]),
            type=str(raw["type"]),
            label=str(raw["label"]),
            options=options,
            system=bool(raw.get("system", False)),
            currency=raw.get("currency"),
            max=raw.get("max"),
            computed=raw.get("computed"),
        )
    except (KeyError, TypeError) as exc:
        raise TemplateError(f"malformed column in {path}: {exc}") from exc


def _check_unique_keys(columns: tuple[ColumnDefinition, ...], path: Path) -> None:
    keys = [c.key for c in columns]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        raise TemplateError(f"duplicate column keys {sorted(duplicates)} in {path}")


_SETTINGS_TYPES: dict[str, tuple[type, ...]] = {
    "integer": (int,),
    "number": (int, float),
    "string": (str,),
    "boolean": (bool,),
}


def instantiate_tracker(
    template: Template,
    settings_values: dict[str, Any],
) -> dict[str, Any]:
    """Build the per-project tracker definition from a template and user settings.

    Settings are validated against the template schema (known key, declared
    type). Unknown settings are rejected rather than ignored — a typo in a
    project setting must surface at creation, not corrupt the definition.
    """
    properties = template.settings_schema.get("properties", {})
    merged = dict(template.settings_defaults)
    for key, value in settings_values.items():
        if key not in properties:
            raise TemplateError(
                f"unknown setting {key!r} for template {template.key!r}"
            )
        expected = properties[key].get("type")
        allowed = _SETTINGS_TYPES.get(str(expected), ())
        if allowed and not isinstance(value, allowed):
            raise TemplateError(
                f"setting {key!r} expects {expected}, got {type(value).__name__}",
            )
        merged[key] = value
    return {
        "template_key": template.key,
        "template_version": template.version,
        "revision": 0,
        "columns": [_column_to_dict(c) for c in template.columns],
        "conditional_rules": [],
        "settings": merged,
    }


def _column_to_dict(column: ColumnDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {
        "key": column.key,
        "type": column.type,
        "label": column.label,
        "system": column.system,
    }
    if column.options is not None:
        result["options"] = [
            {"key": o.key, "label": o.label, **({"color": o.color} if o.color else {})}
            for o in column.options
        ]
    if column.currency is not None:
        result["currency"] = column.currency
    if column.max is not None:
        result["max"] = column.max
    if column.computed is not None:
        result["computed"] = column.computed
    return result
