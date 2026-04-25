import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import get_current_user
from src.common.schemas.auth import UserTokenData

def mock_get_current_user():
    return UserTokenData(
        id="8054aeb2-dc2b-43a7-8a4e-0a4a851eb339",
        email="admin@test.com",
        role="super_admin",
        institution_id=None,
        department_id=None
    )

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
response = client.get('/api/billing/fee-heads?size=100')
print("STATUS:", response.status_code)
try:
    print("BODY:", response.json())
except:
    print("BODY TEXT:", response.text)
