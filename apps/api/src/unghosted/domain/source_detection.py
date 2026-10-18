"""Domain-name to source detection, no fetch (user story 4, item 4).

The mapping lives in `packages/shared/source-domains.json`, shared with the
web app for instant feedback. The API is authoritative.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "shared" / "source-domains.json"
)


def load_source_domains(path: Path = DEFAULT_MAPPING_PATH) -> dict[str, str]:
    """Load the domain → source-key mapping from the shared package."""
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in mapping.items()}


def registrable_domain(host: str) -> str:
    """The last two labels of a hostname (www.indeed.com → indeed.com).

    Deliberately naive: the known job/housing boards do not use public-suffix
    suffixes like co.uk. Single-label hosts return themselves.
    """
    labels = host.lower().rstrip(".").split(".")
    if len(labels) < 2:
        return host.lower().rstrip(".")
    return f"{labels[-2]}.{labels[-1]}"


def detect_source(url: str, mapping: dict[str, str]) -> str:
    """Source key for a URL. Unknown domains map to ``other``."""
    host = urlsplit(url).hostname or ""
    if not host:
        return "other"
    return mapping.get(registrable_domain(host), "other")
