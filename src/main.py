"""
ERP Backend — Application entry point.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from apps import ROUTERS
from core.config import settings
from core.database import (
    async_engine,
    create_schemas,
    ensure_admission_gate_entry_link,
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

add_pagination(app)


# ── Root health-check ─────────────────────────────────
@app.get("/")
@public_route
async def health_check():
    return {"status": "ok"}


@app.exception_handler(IntegrityError)
async def handle_integrity_error(_: Request, exc: IntegrityError):
    """
    Handle database integrity constraint violations with detailed error messages.
    
    Extracts constraint names and field information from SQLAlchemy IntegrityError
    to provide meaningful feedback to clients.
    """
    # Extract the original database error and statement
    original_error = getattr(exc, "orig", exc)
    error_message = str(original_error).lower()
    statement = getattr(exc, "statement", "")
    
    # Log full error details for debugging
    logger.error(
        f"IntegrityError occurred.\nOriginal Error: {original_error}\n"
        f"Statement: {statement}\nMessage: {error_message}"
    )
    
    # Extract constraint name from error message (PostgreSQL format)
    constraint_name = None
    if "constraint \"" in error_message:
        parts = error_message.split("constraint \"")
        if len(parts) > 1:
            constraint_name = parts[1].split("\"")[0]
    
    # Handle specific known constraints
    if (
        "admission_students_aadhaar_number_key" in error_message
        or constraint_name == "admission_students_aadhaar_number_key"
        or ("duplicate key" in error_message and "aadhaar" in error_message)
    ):
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Aadhaar number already exists. Please use the existing gate pass/admission record for this Aadhaar.",
                "constraint": "admission_students_aadhaar_number_key"
            },
        )
    
    # Build generic error response with constraint details if available
    detail = "Database integrity constraint violation"
    response_data = {"detail": detail}
    
    if constraint_name:
        logger.warning(f"Constraint violation: {constraint_name}")
        response_data["constraint"] = constraint_name
        # Try to extract field name from constraint name (e.g., "table_field_key" -> "field")
        if "_key" in constraint_name or "_unique" in constraint_name:
            field = constraint_name.replace("_key", "").replace("_unique", "").split("_")[-1]
            response_data["field"] = field
    else:
        # Fallback: try to extract field info from the error message
        if "duplicate key" in error_message:
            response_data["detail"] = "Duplicate value for a unique field"
        elif "foreign key" in error_message:
            response_data["detail"] = "Invalid reference to related record"
        elif "not null" in error_message:
            response_data["detail"] = "Required field is missing"
    
    return JSONResponse(
        status_code=409,
        content=response_data,
    )


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

    await ensure_admission_gate_entry_link()
    logger.info("Admission schema compatibility ready ✅")

    await seed_initial_data()
    logger.info("Seed data ready ✅")

    ensure_bucket(settings.minio_bucket)
    logger.info("Storage bucket ready ✅")

    yield
    logger.info("Shutdown complete ✅")


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
