import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import get_current_user

def mock_get_current_user():
    return {"id": "dummy", "role": "admin"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
response = client.get('/api/billing/fee-heads?size=100')
print("STATUS:", response.status_code)
