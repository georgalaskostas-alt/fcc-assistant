from fastapi.testclient import TestClient

from app.desktop_server import app


def test_bridge_endpoints_are_available():
    client = TestClient(app)

    capabilities = client.get("/bridge/v1/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["read_only"] is True

    site = client.get("/bridge/v1/site")
    assert site.status_code == 200
    assert site.json()["units"]
