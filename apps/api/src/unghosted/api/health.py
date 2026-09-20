"""Liveness endpoint."""

from litestar import Controller, get


class HealthController(Controller):
    """Reports whether the service is up."""

    path = "/health"

    @get(status_code=200)
    async def health(self) -> dict[str, str]:
        return {"status": "ok"}
