import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import get_current_user

# Mock user dependency to return a dummy user
def mock_get_current_user():
    return {"id": "dummy", "role": "admin"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
response = client.get('/api/billing/financial-years?filters=%7B%22%24and%22%3A%5B%7B%22field%22%3A%22active%22%2C%22operator%22%3A%22%24eq%22%2C%22value%22%3Atrue%7D%5D%7D&size=50')
print("STATUS:", response.status_code)
print("BODY:", response.json())
