"""Litestar application factory."""

from litestar import Litestar

from unghosted.api.health import HealthController


def create_app() -> Litestar:
    """Build the Litestar app. Controllers are grouped under the versioned
    API prefix; everything business-level lands in later phases."""
    return Litestar(path="/api/v1", route_handlers=[HealthController])
