"""
ERP Backend — Application entry point.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

from apps import ROUTERS
from core.config import settings
from core.database import (
    async_engine,
    create_schemas,
    ensure_database_exists,
    seed_initial_data,
    sync_engine,
)
from core.logging import logger
from core.security import AuthMiddleware, get_current_user, public_route
from components.db.base_model import Base
from infrastructure.storage import ensure_bucket


# ── App factory ───────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    swagger_ui_parameters={"persistAuthorization": True},
)

# Middleware — order matters (last added = first executed)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)


# ── Root health-check ─────────────────────────────────
@app.get("/")
@public_route
async def health_check():
    return {"status": "ok"}


# ── Register routers ─────────────────────────────────
for router, prefix in ROUTERS:
    app.include_router(router, prefix=prefix, dependencies=[Depends(get_current_user)])


# ── Lifespan ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database
    if ensure_database_exists():
        logger.info("Database created ✅")
        with sync_engine.begin() as conn:
            create_schemas(conn, Base.metadata)
    else:
        logger.info("Database exists ✅")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables synced ✅")

    await seed_initial_data()
    logger.info("Seed data ready ✅")

    ensure_bucket(settings.minio_bucket)
    logger.info("Storage bucket ready ✅")

    yield
    logger.info("Shutdown complete ✅")


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
