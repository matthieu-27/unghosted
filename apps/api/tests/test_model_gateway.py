"""Mistral gateway: request shape, filtering, unavailability (ADR 0008)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from unghosted.gateways.model import (
    ExtractionTask,
    MistralGateway,
    ModelUnavailableError,
    ProfileDraftTask,
)


def make_gateway(handler: Any) -> MistralGateway:
    gateway = MistralGateway(api_key="test-key", model="mistral-small-latest")
    gateway._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return gateway


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


async def test_extract_fields_filters_to_requested_keys() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return chat_response(json.dumps({"company": "Acme", "hack": "x"}))

    gateway = make_gateway(handler)
    task = ExtractionTask(
        page_kind="job_offer",
        page_text="Data Engineer chez Acme",
        specs=[{"key": "company", "type": "text", "label": "Company"}],
    )
    result = await gateway.extract_fields(task)
    await gateway.close()

    assert result == {"company": "Acme"}
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["model"] == "mistral-small-latest"
    # The page text reaches the model, but the field list scopes the answer.
    assert seen["body"]["messages"][1]["content"].find("Data Engineer") > 0


async def test_extract_fields_wraps_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    gateway = make_gateway(handler)
    with pytest.raises(ModelUnavailableError, match="mistral call failed"):
        await gateway.extract_fields(
            ExtractionTask(
                page_kind="other",
                page_text="text",
                specs=[{"key": "company", "type": "text", "label": "Company"}],
            )
        )
    await gateway.close()


async def test_extract_fields_wraps_bad_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response("not json")

    gateway = make_gateway(handler)
    with pytest.raises(ModelUnavailableError):
        await gateway.extract_fields(
            ExtractionTask(
                page_kind="other",
                page_text="text",
                specs=[{"key": "company", "type": "text", "label": "Company"}],
            )
        )
    await gateway.close()


async def test_classify_kind_accepts_confident_known_kind() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response(json.dumps({"kind": "housing_listing", "confident": True}))

    gateway = make_gateway(handler)
    assert await gateway.classify_kind("Appartement 2 pieces Montreuil") == (
        "housing_listing"
    )
    await gateway.close()


async def test_classify_kind_rejects_unknown_or_unconfident() -> None:
    cases = [
        json.dumps({"kind": "spaceship", "confident": True}),
        json.dumps({"kind": "job_offer", "confident": False}),
    ]
    for content in cases:

        def handler(request: httpx.Request, content: str = content) -> httpx.Response:
            return chat_response(content)

        gateway = make_gateway(handler)
        assert await gateway.classify_kind("text") is None
        await gateway.close()


async def test_draft_profile_sends_only_the_task_documents() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return chat_response(json.dumps({"headline": "Apprentice"}))

    gateway = make_gateway(handler)
    task = ProfileDraftTask(
        project_description="Apprenticeship search",
        document_texts=[{"type_key": "cv", "text": "Python and SQL"}],
    )
    result = await gateway.draft_profile(task)
    await gateway.close()

    user_payload = json.loads(seen["body"]["messages"][1]["content"])
    assert user_payload["project_description"] == "Apprenticeship search"
    assert user_payload["documents"] == [{"type_key": "cv", "text": "Python and SQL"}]
    assert result == {"headline": "Apprentice"}


async def test_draft_profile_keeps_only_well_typed_fields() -> None:
    """Whitelist plus type check: unexpected keys and wrong-typed values
    are dropped before anything reaches a profile row."""
    payload = {
        "headline": "Curious apprentice",
        "seeking": None,  # not a string
        "highlights": ["Fact one", 42],  # mixed list -> rejected
        "style_notes": ["Direct tone"],
        "injected": "should not survive",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response(json.dumps(payload))

    gateway = make_gateway(handler)
    result = await gateway.draft_profile(
        ProfileDraftTask(project_description=None, document_texts=[])
    )
    await gateway.close()

    assert result == {
        "headline": "Curious apprentice",
        "style_notes": ["Direct tone"],
    }
