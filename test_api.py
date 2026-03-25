from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_api_is_alive():
    """Basic smoke test that ensures the backend responds."""
    # Use the auto-generated /docs route to avoid relying on custom logic
    response = client.get("/docs")

    # Expect a 200 HTTP status code indicating success
    assert response.status_code == 200
