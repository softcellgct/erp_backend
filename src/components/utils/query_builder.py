
from typing import List, Type, Optional
from fastapi import Depends, Request
from sqlalchemy import select, or_, asc, desc, cast, String
from fastapi_querybuilder.params import QueryParams
from fastapi_querybuilder.core import parse_filter_query, parse_filters, resolve_and_join_column

def SafeQueryBuilder(model: Type, searchable_fields: Optional[List[str]] = None):
    """
    A custom QueryBuilder that allows restricting search to specific fields,
    preventing infinite recursion and duplicate joins.
    """
    def wrapper(
        request: Request,
        params: QueryParams = Depends()
    ):
        return build_safe_query(model, params, searchable_fields)
    return Depends(wrapper)

def normalize_filters(f):
    """
    Recursively converts frontend filter format:
    {"field": "name", "operator": "$eq", "value": "test"}
    into the format expected by fastapi_querybuilder:
    {"name": {"$eq": "test"}}
    """
    if isinstance(f, dict):
        if "field" in f and "operator" in f and "value" in f:
            return {f["field"]: {f["operator"]: f["value"]}}
        return {k: normalize_filters(v) for k, v in f.items()}
    elif isinstance(f, list):
        return [normalize_filters(item) for item in f]
    return f

def build_safe_query(cls, params: QueryParams, searchable_fields: Optional[List[str]] = None):
    if hasattr(cls, 'deleted_at'):
        query = select(cls).where(cls.deleted_at.is_(None))
    else:
        query = select(cls)

    # Filters
    parsed_filters = parse_filter_query(params.filters)
    if parsed_filters:
        parsed_filters = normalize_filters(parsed_filters)
        filter_expr, query = parse_filters(cls, parsed_filters, query)
        if filter_expr is not None:
            query = query.where(filter_expr)

    # Search
    if params.search and searchable_fields:
        search_expr = []
        joins = {} # Keep track of joins for search to avoid duplicates if possible, though resolve_and_join_column handles it partially

        for field in searchable_fields:
            if "." in field:
                # Nested field (e.g. institution.name)
                nested_keys = field.split(".")
                # We need to manually handle joins or use resolve_and_join_column
                # Note: resolve_and_join_column returns (column, query) and updates joins dict
                # However, reusing it linearly might chain joins. 
                # For OR conditions, we typically want left joins to be shared.
                
                # Careful: resolve_and_join_column modifies the query to add joins.
                # If we do this for each field in an OR block, we might get multiple joins or messy query state if not careful.
                # But since we are building a single list of expressions, we must ensure the query has the necessary joins.
                try:
                    column, query = resolve_and_join_column(cls, nested_keys, query, joins)
                    search_expr.append(cast(column, String).ilike(f"%{params.search}%"))
                except Exception:
                     # Ignore invalid fields in search to prevent crashing
                     pass
            else:
                # Direct field
                column = getattr(cls, field, None)
                if column is not None:
                    search_expr.append(cast(column, String).ilike(f"%{params.search}%"))
        
        if search_expr:
            query = query.where(or_(*search_expr))
            # Use DISTINCT ON the model primary key to avoid DISTINCT across
            # all selected columns (which can include JSON types lacking
            # an equality operator). This produces PostgreSQL DISTINCT ON (id).
            pk = getattr(cls, "id", None)
            if pk is not None:
                query = query.distinct(pk)
            else:
                query = query.distinct()
            
    elif params.search:
        # Fallback to default recursive search if no fields provided? 
        # Or just do nothing? 
        # Let's fallback to basic string columns of the model only, to be safe but useful.
        search_expr = []
        for column in cls.__table__.columns:
             if isinstance(column.type, String):
                  search_expr.append(column.ilike(f"%{params.search}%"))
        
        if search_expr:
            query = query.where(or_(*search_expr))

    # Sorting
    if params.sort:
        try:
            sort_field, sort_dir = params.sort.split(":")
        except ValueError:
            sort_field, sort_dir = params.sort, "asc"

        column = getattr(cls, sort_field, None)
        if column is None:
            nested_keys = sort_field.split(".")
            if len(nested_keys) > 1:
                joins = {} # New joins dict for sort
                column, query = resolve_and_join_column(
                    cls, nested_keys, query, joins)
            else:
                # raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")
                pass # Ignore invalid sort

        if column is not None:
            query = query.order_by(
                asc(column) if sort_dir.lower() == "asc" else desc(column))

    return query
