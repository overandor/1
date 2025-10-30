from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

def test_create_kpi():
    response = client.post("/kpis/", json={"id": "test_kpi", "name": "Test KPI", "description": "A test KPI", "formula": "test"})
    assert response.status_code == 200
    assert response.json()["name"] == "Test KPI"

def test_list_kpis():
    response = client.get("/kpis/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
