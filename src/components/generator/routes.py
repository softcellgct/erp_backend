from fastapi import APIRouter, HTTPException, Query, Depends, Path, Request, status
from components.db.base_model import Base
from components.db.db import get_db_session
from fastapi_pagination.ext.sqlalchemy import paginate
from components.generator.schema.registry import get_schemas
from fastapi_pagination import Page, add_pagination
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
import re
from components.utils.query_builder import SafeQueryBuilder


def create_crud_routes(
    model: Base,
    CreateSchema=None,
    UpdateSchema=None,
    AllResponseSchema=None,
    IdResponseSchema=None,
    decorators=None,
    apply_decorators_on_read: bool = True,
) -> APIRouter:
    SchemaCreate = CreateSchema or get_schemas(model)[0]
    SchemaUpdate = UpdateSchema or get_schemas(model)[1]
    SchemaAllResponse = AllResponseSchema or get_schemas(model)[2]
    SchemaIdResponse = IdResponseSchema or AllResponseSchema or get_schemas(model)[3]

    # Split model.__name__ at uppercase letters and join as separate words
    split_name = " ".join(re.findall(r"[A-Z][a-z]*", model.__name__))
    snake_case_key = "_".join(split_name.lower().split())

    # Create a router with the model name as the tag
    router: APIRouter = APIRouter()

    # Generator Keys
    """
    *:*:get_all
    *:*:get_one
    *:*:create
    *:*:update
    *:*:delete
    """

    """
    =====================================================
    #  Route for retrieving all records with pagination, filtering, sorting, and searching
    =====================================================
    """

    @router.get(
        "",
        response_model=Page[SchemaAllResponse],
        name=f"{model}:{snake_case_key}:get_all",
        description=f"Retrieve paginated {split_name} records with optional filtering, sorting, and searching.",
    )
    async def read_all(
        request: Request,
        db: AsyncSession = Depends(get_db_session),
        query=SafeQueryBuilder(model),
    ):
        """
        Retrieve paginated {split_name} records with optional filtering, sorting, and searching.
        """
        # Use DISTINCT ON the primary key to avoid DISTINCT across all selected
        # columns (which can include types like JSON without equality ops).
        pk = getattr(model, "id", None)
        if pk is not None:
            query = query.distinct(pk)

            # PostgreSQL requires that DISTINCT ON expressions match the initial
            # ORDER BY expressions. If the query has an ORDER BY that doesn't
            # start with the primary key, prepend the primary key to the
            # ordering clause so DISTINCT ON works correctly.
            try:
                existing_order_by = getattr(query, "_order_by_clause", None)
                if existing_order_by is not None and len(existing_order_by) > 0:
                    # Clear existing ORDER BY and reapply with pk first
                    query = query.order_by(None)
                    query = query.order_by(pk, *list(existing_order_by))
                else:
                    # No explicit order_by present — ensure we at least order by pk
                    query = query.order_by(pk)
            except Exception:
                # If anything goes wrong, fall back to distinct without modifying order
                pass
        else:
            query = query.distinct()

        response_data = await paginate(db, query)
        return response_data

    """
    =====================================================
    #  Route for retrieving a single record by ID
    =====================================================
    """

    @router.get(
        "/{id}",
        response_model=SchemaIdResponse,
        status_code=status.HTTP_200_OK,
        name=f"{model}:{snake_case_key}:get_one",
        description=f"Retrieve a single {split_name} record by its ID.",
    )
    async def read_one(
        request: Request,
        id: UUID = Path(
            ..., description=f"The ID (UUID) of the {split_name} record to retrieve."
        ),
        db: AsyncSession = Depends(get_db_session),
    ):
        """
        Retrieve a single {split_name} record by its ID.
        """
        # `id` is validated/converted to UUID by FastAPI before calling the service
        data = await model.get_record_by_id(db, id)
        if not data:
            raise HTTPException(
                status_code=404, detail=f"{split_name} with ID {id} not found"
            )
        return data

    """
    =====================================================
    # Route for creating multiple records in bulk
    =====================================================
    """

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        name=f"{model}:{snake_case_key}:create",
        description=f"Create new {split_name} records in the database.",
    )
    async def bulk_create(
        request: Request,
        items: List[SchemaCreate],
        db: AsyncSession = Depends(get_db_session),
    ):
        """
        Create multiple new {split_name} records in bulk and invalidate cached list.
        """
        result = await model.create(request, db, items)
        
        # Handle both old (int) and new (dict) return formats
        if isinstance(result, dict):
            return {
                "detail": f"{split_name} data created successfully",
                "created": result.get("created", 0),
                "ids": result.get("ids", []),
                "skipped": result.get("skipped", 0),
                "errors": result.get("errors", []),
            }
        else:
            # Legacy format - just a count
            return {
                "detail": f"{split_name} data created successfully",
                "count": result,
            }

    """
    =====================================================
    # Route for updating multiple records in bulk
    =====================================================
    """

    @router.put(
        "",
        status_code=status.HTTP_200_OK,
        name=f"{model}:{snake_case_key}:update",
        description=f"Update multiple existing {split_name} records in bulk.",
    )
    async def bulk_update(
        request: Request,
        items: list[SchemaUpdate],
        db: AsyncSession = Depends(get_db_session),
    ):
        """
        Update multiple existing {split_name} records in bulk.
        """
        if not items:
            raise HTTPException(
                status_code=400, detail=f"No {split_name} data provided for update"
            )

        count = await model.update(request, db, items)
        if count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No matching {split_name} records found for update",
            )
        return {"detail": f"{split_name} data updated successfully", "count": count}

    """
    =====================================================
    # Route for deleting multiple records in bulk
    =====================================================
    """

    @router.delete(
        "",
        status_code=status.HTTP_200_OK,
        name=f"{model}:{snake_case_key}:delete",
        description=f"Delete multiple {split_name} records by their IDs.",
    )
    async def bulk_delete(
        request: Request,
        ids: list[UUID],
        hard_delete: bool = Query(
            False,
            description=f"Set to True for hard delete (only allowed for SUPERADMIN) on {split_name} records",
        ),
        db: AsyncSession = Depends(get_db_session),
    ):
        """
        Delete multiple {split_name} records by their IDs.
        """
        if not ids:
            raise HTTPException(
                status_code=400, detail=f"No {split_name} IDs provided for deletion"
            )

        # Get user role from request

        if hard_delete:
            result = await model.hard_delete(db, ids)
        else:
            result = await model.soft_delete(request, db, ids)

        if result == 0:
            raise HTTPException(
                status_code=404, detail=f"No matching {split_name} records found"
            )

        return {
            "detail": f"{split_name} data deleted successfully",
            "count": result,
        }

    # Apply decorators to all routes if provided
    if decorators:
        for route in router.routes:
            if hasattr(route, 'endpoint') and callable(route.endpoint):
                methods = getattr(route, "methods", set()) or set()
                is_read_route = "GET" in methods
                if is_read_route and not apply_decorators_on_read:
                    continue

                # Apply each decorator in the order provided
                decorated_endpoint = route.endpoint
                for decorator in decorators:
                    decorated_endpoint = decorator(decorated_endpoint)
                route.endpoint = decorated_endpoint

    return add_pagination(router)
