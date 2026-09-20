"""Health endpoint contract."""

from litestar.testing import TestClient

from unghosted.app import create_app


def test_health_endpoint_returns_ok() -> None:
    with TestClient(app=create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
