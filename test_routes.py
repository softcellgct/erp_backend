import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
response = client.get("/api/meta/religions")
print("Response status:", response.status_code)
print("Response json:", response.json() if response.status_code == 200 else response.text)
