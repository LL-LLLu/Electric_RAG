import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_search_empty_query():
    response = client.get("/api/search/", params={"q": ""})
    assert response.status_code == 422


def test_search_valid_query():
    response = client.get("/api/search/", params={"q": "FAN-101"})
    assert response.status_code == 200
    assert "results" in response.json()


def test_equipment_list():
    response = client.get("/api/equipment/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_documents_list():
    response = client.get("/api/documents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
