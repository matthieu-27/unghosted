"""Model eligibility (ADR 0009). Pure domain.

Every model-call service resolves its input documents and calls
``ensure_model_eligible`` before touching the gateway. The test suite
asserts the gateway is never called with an ineligible document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class DocumentRef:
    """What the domain needs to know about a document for eligibility:
    its type key and its snapshot flag (documents.model_eligible)."""

    type_key: str
    model_eligible: bool


class IneligibleDocumentError(ValueError):
    """An input document is not model-eligible; the call never starts."""

    def __init__(self, type_keys: Sequence[str]) -> None:
        super().__init__(
            "documents are not model-eligible: " + ", ".join(sorted(set(type_keys)))
        )
        self.type_keys = list(type_keys)


def ensure_model_eligible(refs: Sequence[DocumentRef]) -> None:
    """Raise before any gateway call if any input document is ineligible."""
    ineligible = [r.type_key for r in refs if not r.model_eligible]
    if ineligible:
        raise IneligibleDocumentError(ineligible)
