import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import get_current_user

def mock_get_current_user():
    return {"id": "dummy", "role": "admin"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
# new format
response = client.get('/api/billing/fee-heads?filters={"$and":[{"academic_year_id":{"$eq":"68a805d8-438c-44e3-bd58-9094bf26a0f9"}},{"institution_id":{"$eq":"82917b80-732e-4299-9af5-d34b84b19123"}}]}&size=100')
print("STATUS:", response.status_code)
print("BODY:", response.json())
