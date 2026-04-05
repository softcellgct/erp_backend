import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import app
from fastapi.testclient import TestClient
from core.security import get_current_user

class MockUser:
    id = "00000000-0000-0000-0000-000000000000"
    is_active = True
    is_superuser = True

async def mock_user():
    return MockUser()

app.dependency_overrides[get_current_user] = mock_user
client = TestClient(app)
try:
    response = client.get("/api/meta/religions")
    print("Status:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Error:", str(e))
