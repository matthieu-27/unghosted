"""Link analysis: input detection, page kind, structured extraction, source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from unghosted.domain.link_analysis import (
    InputNotProvidedError,
    clean_html,
    detect_input,
    detect_page_kind,
    extract_structured,
    model_field_specs,
)
from unghosted.domain.source_detection import detect_source, load_source_domains

SHARED = Path(__file__).resolve().parents[3] / "packages" / "shared"

JOB_HINTS = [
    "date_sent",
    "company",
    "position",
    "listing_url",
    "location",
    "contract_type",
    "source",
    "status",
    "salary_range_advertised",
    "notes",
]

JOB_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "JobPosting",
 "title": "Data Engineer",
 "hiringOrganization": {"name": "Acme SAS"},
 "jobLocation": {"address": {"addressLocality": "Nantes",
                             "addressRegion": "Pays de la Loire"}},
 "baseSalary": {"currency": "EUR",
                "value": {"value": 45000, "unitText": "YEAR"}},
 "employmentType": "FULL_TIME"}
</script>
</head><body><p>Nous cherchons un·e ingénieur·e data.</p></body></html>
"""

RENT_HTML = """
<html><head><title>Appartement 2 pièces Montreuil</title>
<meta property="og:title" content="Appartement 2 pièces Montreuil">
<meta property="og:type" content="product">
</head><body>Loyer 980 EUR charges comprises.</body></html>
"""


# --- input detection ---------------------------------------------------------


def test_detect_url() -> None:
    assert detect_input("https://example.com/job/123") == "url"
    assert detect_input(" http://example.com ") == "url"


def test_detect_text_when_spaced_or_not_a_url() -> None:
    assert detect_input("Data Engineer chez Acme à Nantes, 45k€") == "text"
    assert detect_input("www.example.com/job") == "text"  # no scheme


def test_detect_empty_raises() -> None:
    with pytest.raises(InputNotProvidedError):
        detect_input("   ")


# --- page kind ---------------------------------------------------------------


def test_kind_jsonld_job_posting_wins() -> None:
    verdict = detect_page_kind(JOB_HTML, "https://boards.example.com/x")
    assert verdict is not None
    assert (verdict.kind, verdict.confidence, verdict.basis) == (
        "job_offer",
        "high",
        "jsonld",
    )


def test_kind_open_graph_rent() -> None:
    verdict = detect_page_kind(RENT_HTML, "https://seloger.com/rent/123")
    assert verdict is not None
    assert verdict.kind == "housing_listing"
    assert verdict.basis == "open_graph"


def test_kind_url_pattern_fallback() -> None:
    verdict = detect_page_kind("<html></html>", "https://x.com/offre-emploi/42")
    assert verdict is not None
    assert (verdict.kind, verdict.basis) == ("job_offer", "url_pattern")


def test_kind_inconclusive_returns_none() -> None:
    assert detect_page_kind("<html></html>", "https://x.com/") is None


# --- structured extraction ---------------------------------------------------


def test_extract_job_jsonld_fields_with_provenance() -> None:
    fields = extract_structured(JOB_HTML, "https://boards.example.com/x", JOB_HINTS)
    by_key = {f.column_key: f for f in fields}
    assert by_key["position"].value == "Data Engineer"
    assert by_key["position"].provenance == "structured"
    assert by_key["company"].value == "Acme SAS"
    assert "Nantes" in by_key["location"].value
    assert "45000" in by_key["salary_range_advertised"].value
    assert by_key["listing_url"].provenance == "detection"
    assert by_key["notes"].provenance == "detection"


def test_extract_skips_columns_outside_hints() -> None:
    fields = extract_structured(JOB_HTML, "https://x.com/", ["company"])
    assert [f.column_key for f in fields] == ["company"]


def test_extract_malformed_jsonld_is_skipped() -> None:
    html = '<script type="application/ld+json">{broken</script>' + RENT_HTML
    fields = extract_structured(html, "https://x.com/", ["position", "notes"])
    assert {f.column_key for f in fields} == {"position", "notes"}


def test_extract_og_title_used_when_no_jsonld() -> None:
    fields = extract_structured(RENT_HTML, "https://x.com/", ["position"])
    by_key = {f.column_key: f for f in fields}
    assert by_key["position"].value == "Appartement 2 pièces Montreuil"
    assert by_key["position"].provenance == "meta"


# --- model specs -------------------------------------------------------------


def test_model_specs_cover_unfilled_hints_only() -> None:
    columns: list[dict[str, Any]] = [
        {"key": "company", "type": "text", "label": "Company"},
        {
            "key": "status",
            "type": "select",
            "label": "Status",
            "options": [{"key": "sent", "label": "Sent"}],
        },
        {
            "key": "days_since_sent",
            "type": "computed",
            "label": "Days",
            "computed": "x",
        },
        {"key": "response_date", "type": "date", "label": "Response", "system": True},
        {"key": "cv", "type": "document-link", "label": "CV"},
    ]
    specs = model_field_specs(
        columns,
        ["company", "status", "days_since_sent", "response_date", "cv"],
        filled_keys={"company"},
    )
    assert [s["key"] for s in specs] == ["status"]
    assert specs[0]["options"] == ["sent"]


# --- source detection --------------------------------------------------------


def test_source_detection_known_domains_and_subdomains() -> None:
    mapping = load_source_domains(SHARED / "source-domains.json")
    assert detect_source("https://www.indeed.com/viewjob?jk=1", mapping) == "indeed"
    assert detect_source("https://m.leboncoin.fr/locations/1", mapping) == "leboncoin"
    assert detect_source("https://fr.indeed.com/job/1", mapping) == "indeed"


def test_source_detection_unknown_is_other() -> None:
    mapping = load_source_domains(SHARED / "source-domains.json")
    assert (
        detect_source("https://some-random-board.example/offre/1", mapping) == "other"
    )


# --- cleaning ----------------------------------------------------------------


def test_clean_html_strips_scripts_and_tags() -> None:
    html = "<head><script>evil()</script><style>a{}</style></head><p>Hello &amp;   world</p>"
    assert clean_html(html) == "Hello & world"
