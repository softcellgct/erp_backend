from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
import uvicorn
from apps import ROUTERS
from components.db.base_model import Base
from logs.logging import logger
from components.middleware import PermissionMiddleware, get_current_user, public_route
from fastapi.middleware.cors import CORSMiddleware
from components.db.db import (
    create_database_if_not_exists,
    create_roles_and_users,
    db_engine,
    setup_schemas,
    sync_engine,
)

app = FastAPI(swagger_ui_parameters={"persistAuthorization": True})

app.add_middleware(PermissionMiddleware)


"""
=====================================================
# Middleware setup things happens here
=====================================================
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
@public_route
async def read_root():
    return {"Hello": "World"}


for router, prefix in ROUTERS:
    app.include_router(router, prefix=prefix, dependencies=[Depends(get_current_user)])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the database exists before starting the application
    if create_database_if_not_exists():
        logger.info("Database created successfully ✅")
        with sync_engine.begin() as conn:
            setup_schemas(conn, Base.metadata)
    else:
        logger.info("Database already exists")

    
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL Database connected successfully.✅")

    await create_roles_and_users()
    logger.info("Database roles and initial users are set up.✅")

    yield

    logger.info("Application exited successfully.✅")


app.router.lifespan_context = lifespan

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
