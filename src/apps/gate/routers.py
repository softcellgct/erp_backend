from fastapi import APIRouter, Request
from components.middleware import public_route

router = APIRouter()


@router.get("/check",
            name="Health Check",
            description="A simple health check endpoint to verify the service is running.",
            )
def check(request: Request):
    return {"status": "ok", "request": request}
