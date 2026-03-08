import uuid
from typing import Any, List, Optional

from fastapi import Request
from sqlalchemy import UUID, DateTime, ForeignKey, Index, delete, func, select, update
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import Mapped, mapped_column, defer, selectinload,raiseload
from sqlalchemy.ext.asyncio import AsyncSession


# Audit fields to exclude from nested objects
_AUDIT_FIELDS = {"created_at", "updated_at", "deleted_at", "created_by", "updated_by", "deleted_by"}


def _convert_nested_rels(model_class, data: dict, session=None) -> dict:
    """
    Recursively walk *data* and convert any dict / list-of-dicts that
    correspond to a SQLAlchemy relationship on *model_class* into proper
    model instances.  Works at arbitrary nesting depth.

    * to-one  (uselist=False) : dict  → model instance
    * to-many (uselist=True)  : [dict, …] → [model instance, …]

    Already-materialised SA instances (have ``_sa_instance_state``) are
    left untouched.  Audit columns are stripped before constructing new
    instances so server defaults apply.
    """
    from sqlalchemy.inspection import inspect

    mapper = inspect(model_class)
    for rel_name, rel in mapper.relationships.items():
        if rel_name not in data or data[rel_name] is None:
            continue

        rel_data = data[rel_name]
        related_model = rel.mapper.class_

        if not rel.uselist:
            # ---- to-one ----
            if isinstance(rel_data, dict):
                cleaned = {k: v for k, v in rel_data.items() if k not in _AUDIT_FIELDS}
                # recurse before constructing the instance
                cleaned = _convert_nested_rels(related_model, cleaned, session)
                obj = related_model(**cleaned)
                if session is not None:
                    session.add(obj)
                data[rel_name] = obj
            # already a model instance → leave it
        else:
            # ---- to-many ----
            if isinstance(rel_data, list):
                new_list = []
                for item in rel_data:
                    if isinstance(item, dict):
                        cleaned = {k: v for k, v in item.items() if k not in _AUDIT_FIELDS}
                        cleaned = _convert_nested_rels(related_model, cleaned, session)
                        obj = related_model(**cleaned)
                        if session is not None:
                            session.add(obj)
                        new_list.append(obj)
                    elif hasattr(item, "_sa_instance_state"):
                        new_list.append(item)
                    else:
                        raise ValueError(
                            f"Invalid related item for relationship '{rel_name}': {item}"
                        )
                data[rel_name] = new_list

    return data


async def _convert_nested_rels_for_update(
    model_class, data: dict, session: AsyncSession
) -> dict:
    """
    Like ``_convert_nested_rels`` but *update-aware*: when a nested dict
    carries an ``id`` key the existing row is fetched and updated in-place
    instead of creating a new instance.  Recurses to any depth.
    """
    from sqlalchemy.inspection import inspect

    mapper = inspect(model_class)
    for rel_name, rel in mapper.relationships.items():
        if rel_name not in data or data[rel_name] is None:
            continue

        rel_data = data[rel_name]
        related_model = rel.mapper.class_

        if not rel.uselist:
            # ---- to-one ----
            if isinstance(rel_data, dict):
                data[rel_name] = await _dict_to_instance(
                    related_model, rel_data, session
                )
        else:
            # ---- to-many ----
            if isinstance(rel_data, list):
                new_list = []
                for item in rel_data:
                    if isinstance(item, dict):
                        new_list.append(
                            await _dict_to_instance(related_model, item, session)
                        )
                    elif hasattr(item, "_sa_instance_state"):
                        new_list.append(item)
                    else:
                        raise ValueError(
                            f"Invalid related item for relationship '{rel_name}': {item}"
                        )
                data[rel_name] = new_list

    return data


async def _dict_to_instance(model_class, data: dict, session: AsyncSession):
    """
    Convert a single dict into a model instance.
    * If the dict contains ``id``, fetch the existing row and patch it.
    * Otherwise create a new instance.
    Sub-relationships are converted recursively first.
    """
    from sqlalchemy.inspection import inspect
    from sqlalchemy.orm import raiseload

    if data.get("id"):
        res = await session.execute(
            select(model_class).where(model_class.id == data["id"]).options(raiseload("*"))
        )
        existing = res.scalars().one_or_none()
        if existing:
            mapper = inspect(model_class)
            for key, val in data.items():
                if key == "id" or (key not in mapper.columns and key not in mapper.relationships):
                    continue
                if key in mapper.relationships:
                    rel = mapper.relationships[key]
                    related_model = rel.mapper.class_
                    if not rel.uselist:
                        if val is None:
                            setattr(existing, key, None)
                        elif isinstance(val, dict):
                            setattr(existing, key, await _dict_to_instance(related_model, val, session))
                        elif hasattr(val, "_sa_instance_state"):
                            setattr(existing, key, val)
                    else:
                        if val is None:
                            setattr(existing, key, None)
                        elif isinstance(val, list):
                            items = []
                            for item in val:
                                if isinstance(item, dict):
                                    items.append(await _dict_to_instance(related_model, item, session))
                                elif hasattr(item, "_sa_instance_state"):
                                    items.append(item)
                                else:
                                    raise ValueError(
                                        f"Invalid related item for relationship '{key}': {item}"
                                    )
                            setattr(existing, key, items)
                else:
                    setattr(existing, key, val)
            return existing

    # No id or id not found → create new instance
    cleaned = {k: v for k, v in data.items() if k not in _AUDIT_FIELDS}
    cleaned = await _convert_nested_rels_for_update(model_class, cleaned, session)
    obj = model_class(**cleaned)
    session.add(obj)
    return obj


@as_declarative()
class Base:  # noqa: F811
    """
    =====================================================
    # Base model to include default columns for all tables.
    # Every table gets: UUID PK, audit timestamps, soft-delete,
    # and a partial index on deleted_at for fast active-record lookups.
    =====================================================
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )


    """
    =====================================================
    # Bulk insert multiple records
    =====================================================
    """

    @classmethod
    async def create(
        cls, request: Request, session: AsyncSession, data_list: List[Any]
    ):
        from components.generator.utils.get_user_from_request import get_user_id

        if not data_list:
            raise ValueError("No data provided to create records.")

        objects = []
        for data in data_list:
            user_id = await get_user_id(request)
            obj_data = data.dict() if hasattr(data, "dict") else data
            obj_data["created_by"] = user_id

            # Recursively convert nested relationship dicts → model instances
            obj_data = _convert_nested_rels(cls, obj_data, session)

            # remove any keys that aren't actual columns or relationships on the model
            from sqlalchemy.inspection import inspect
            mapper = inspect(cls)
            valid_keys = set(mapper.columns.keys()) | set(mapper.relationships.keys())
            filtered_data = {k: v for k, v in obj_data.items() if k in valid_keys}

            objects.append(cls(**filtered_data))

        session.add_all(objects)
        await session.commit()

        return len(objects)

    """
    =====================================================
    # Bulk update multiple records, each with different values.
    =====================================================
    """

    @classmethod
    async def update(
        cls, request: Request, session: AsyncSession, data_list: List[dict]
    ):
        from components.generator.utils.get_user_from_request import get_user_id
        from sqlalchemy.inspection import inspect

        if not data_list:
            raise ValueError("No data provided for update.")

        user_id = await get_user_id(request)

        # Extract and validate IDs
        obj_ids = []
        for data_obj in data_list:
            data = (
                data_obj.dict(exclude_unset=True)
                if hasattr(data_obj, "dict")
                else data_obj
            )
            obj_id = data.get("id")
            if not obj_id:
                raise ValueError("Each object must have an 'id' field.")
            obj_ids.append(obj_id)

        # Fetch all existing records
        # Note: Don't use raiseload("*") here as it prevents relationship access
        # The model's relationship lazy loading strategy will be used instead
        result = await session.execute(
            select(cls).where(cls.id.in_(obj_ids), cls.deleted_at.is_(None))
        )
        existing_objs = result.scalars().all()
        existing_objs_map = {obj.id: obj for obj in existing_objs}

        # Check for missing records
        missing_ids = [oid for oid in obj_ids if oid not in existing_objs_map]
        if missing_ids:
            raise ValueError(f"Records with IDs {missing_ids} not found or deleted.")

        # Update each instance
        updated_count = 0
        for data_obj in data_list:
            data = (
                data_obj.dict(exclude_unset=True)
                if hasattr(data_obj, "dict")
                else data_obj
            )
            obj_id = data.pop("id")
            instance = existing_objs_map[obj_id]

            # Inspect mapper to handle nested relationship payloads (dicts/lists)
            mapper = inspect(type(instance))

            for key, value in data.items():
                # Check if key exists in mapper columns or relationships without triggering lazy load
                if key not in mapper.columns and key not in mapper.relationships:
                    continue

                # If this key is a relationship, convert dicts/lists into model instances
                if key in mapper.relationships:
                    rel = mapper.relationships[key]
                    related_model = rel.mapper.class_

                    # Handle to-one relationships
                    if not rel.uselist:
                        if value is None:
                            setattr(instance, key, None)
                        elif isinstance(value, dict):
                            # For to-one relationships, if dict has no id but there's a unique
                            # FK, query for the existing related object
                            if not value.get("id"):
                                # Get the foreign key columns to find existing related object
                                local_cols = list(rel.local_columns)
                                if local_cols:
                                    fk_col = local_cols[0]
                                    fk_value = getattr(instance, fk_col.name, None)
                                    if fk_value:
                                        # Query for existing related object by FK value
                                        # remote_side may be a set; iterate safely to get a column
                                        remote_col = None
                                        if rel.remote_side:
                                            # rel.remote_side could be a set or list
                                            try:
                                                remote_col = next(iter(rel.remote_side))
                                            except TypeError:
                                                # fallback if not iterable
                                                remote_col = None
                                        if remote_col is not None:
                                            res = await session.execute(
                                                select(related_model)
                                                .where(getattr(related_model, remote_col.name) == fk_value)
                                                .options(raiseload("*"))
                                            )
                                        else:
                                            res = None
                                        existing_related = None
                                        if res:
                                            existing_related = res.scalars().one_or_none()
                                        if existing_related and hasattr(existing_related, "id"):
                                            value["id"] = existing_related.id
                            
                            setattr(
                                instance,
                                key,
                                await _dict_to_instance(related_model, value, session),
                            )
                        elif hasattr(value, "_sa_instance_state"):
                            setattr(instance, key, value)
                        else:
                            # scalar FK value
                            setattr(instance, key, value)

                    # Handle to-many relationships
                    else:
                        if value is None:
                            setattr(instance, key, None)
                        elif isinstance(value, list):
                            new_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    new_list.append(
                                        await _dict_to_instance(
                                            related_model, item, session
                                        )
                                    )
                                elif hasattr(item, "_sa_instance_state"):
                                    new_list.append(item)
                                else:
                                    raise ValueError(
                                        f"Invalid related item for relationship '{key}': {item}"
                                    )
                            setattr(instance, key, new_list)
                        else:
                            raise ValueError(
                                f"Invalid value for relationship '{key}': must be list or None"
                            )

                else:
                    # Not a relationship - assign directly
                    setattr(instance, key, value)

            # Set audit field
            if hasattr(instance, "updated_by"):
                instance.updated_by = user_id
            updated_count += 1

        await session.commit()
        return updated_count

    """
    =====================================================
    # Soft delete records by updating deleted_at timestamp instead of deleting them.
    =====================================================
    """

    @classmethod
    async def soft_delete(
        cls, request: Request, session: AsyncSession, ids: List[uuid.UUID]
    ):
        from components.generator.utils.get_user_from_request import get_user_id

        if not ids:
            raise ValueError("No IDs provided to delete records.")

        user_id = await get_user_id(request)

        # Exclude already soft-deleted records
        stmt = (
            update(cls)
            .where(cls.id.in_(ids), cls.deleted_at.is_(None))
            .values(
                deleted_at=func.now(), deleted_by=user_id
            )  # Soft delete by setting timestamp and user
            .execution_options(synchronize_session=False)
        )
        result = await session.execute(stmt)
        await session.commit()

        return result.rowcount

    """
    =====================================================
    # Permanently delete records from the database.
    =====================================================
    """

    @classmethod
    async def hard_delete(cls, session: AsyncSession, ids: List[uuid.UUID]):
        if not ids:
            return 0  # No IDs provided

        stmt = delete(cls).where(cls.id.in_(ids))
        result = await session.execute(stmt)
        await session.commit()

        return result.rowcount

    """
    =====================================================
    # Get only non-deleted (active) record by ID with optional include feature.
    =====================================================
    """

    @classmethod
    async def get_record_by_id(cls, session: AsyncSession, record_id: uuid.UUID):
        query = select(cls).where(cls.deleted_at.is_(None), cls.id == record_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()