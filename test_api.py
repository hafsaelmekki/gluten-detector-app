from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_api_fonctionne():
    """Test très simple pour vérifier que le backend est en vie"""
    # On teste la route /docs car elle est auto-générée par FastAPI
    response = client.get("/docs")

    # On s'attend à ce que le code HTTP soit 200 (Succès)
    assert response.status_code == 200
