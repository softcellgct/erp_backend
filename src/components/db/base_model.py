import uuid
from typing import Any, List, Optional

from fastapi import Request
from sqlalchemy import UUID, DateTime, ForeignKey, Index, delete, func, select, update
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

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
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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
        from sqlalchemy.inspection import inspect

        if not data_list:
            raise ValueError("No data provided to create records.")

        # Audit fields to exclude from nested objects
        AUDIT_FIELDS = {"created_at", "updated_at", "deleted_at", "created_by", "updated_by", "deleted_by"}

        objects = []
        for data in data_list:
            user_id = await get_user_id(request)
            obj_data = data.dict() if hasattr(data, "dict") else data
            obj_data["created_by"] = user_id
            
            # Handle nested relationships - convert dicts/lists to model instances
            mapper = inspect(cls)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in obj_data and obj_data[rel_name] is not None:
                    rel_data = obj_data[rel_name]
                    related_model = rel.mapper.class_
                    # If a single related object is provided as a dict -> create instance
                    if not rel.uselist and isinstance(rel_data, dict):
                        # Remove audit fields from nested data to let server_default handle them
                        cleaned_data = {k: v for k, v in rel_data.items() if k not in AUDIT_FIELDS}
                        obj_data[rel_name] = related_model(**cleaned_data)
                    # If a list of related objects is provided -> convert each
                    elif rel.uselist and isinstance(rel_data, list):
                        new_list = []
                        for item in rel_data:
                            if isinstance(item, dict):
                                # Remove audit fields from nested data to let server_default handle them
                                cleaned_item = {k: v for k, v in item.items() if k not in AUDIT_FIELDS}
                                new_list.append(related_model(**cleaned_item))
                            elif hasattr(item, '_sa_instance_state'):
                                new_list.append(item)
                            else:
                                raise ValueError(f"Invalid related item for relationship '{rel_name}': {item}")
                        obj_data[rel_name] = new_list
                    # If a single related primary key is provided, leave it (FK column should be used instead)
                    else:
                        # leave as-is; let SQLAlchemy or FK column handle it
                        pass
            
            objects.append(cls(**obj_data))

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

        # Audit fields to exclude from nested objects
        AUDIT_FIELDS = {"created_at", "updated_at", "deleted_at", "created_by", "updated_by", "deleted_by"}

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
                if not hasattr(instance, key):
                    continue

                # If this key is a relationship, convert dicts/lists into model instances
                if key in mapper.relationships:
                    rel = mapper.relationships[key]
                    related_model = rel.mapper.class_

                    # Handle to-one relationships
                    if not rel.uselist:
                        if value is None:
                            setattr(instance, key, None)

                        # If a dict is provided, try to reuse existing record when 'id' present
                        elif isinstance(value, dict):
                            if value.get("id"):
                                # try to fetch existing related record
                                res = await session.execute(select(related_model).where(related_model.id == value["id"]))
                                related_obj = res.scalars().one_or_none()
                                if related_obj:
                                    # update fields provided in the dict on the related object
                                    for r_key, r_val in value.items():
                                        if r_key == "id":
                                            continue
                                        if hasattr(related_obj, r_key):
                                            setattr(related_obj, r_key, r_val)
                                    setattr(instance, key, related_obj)
                                else:
                                    # Remove audit fields from nested data
                                    cleaned_value = {k: v for k, v in value.items() if k not in AUDIT_FIELDS}
                                    new_obj = related_model(**cleaned_value)
                                    session.add(new_obj)
                                    setattr(instance, key, new_obj)

                            else:
                                # Remove audit fields from nested data
                                cleaned_value = {k: v for k, v in value.items() if k not in AUDIT_FIELDS}
                                new_obj = related_model(**cleaned_value)
                                session.add(new_obj)
                                setattr(instance, key, new_obj)

                        elif hasattr(value, "_sa_instance_state"):
                            setattr(instance, key, value)
                        else:
                            # If a primary key or scalar is provided, let the FK column handle it
                            setattr(instance, key, value)

                    # Handle to-many relationships
                    else:
                        if value is None:
                            setattr(instance, key, None)
                        elif isinstance(value, list):
                            new_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    if item.get("id"):
                                        res = await session.execute(select(related_model).where(related_model.id == item["id"]))
                                        related_obj = res.scalars().one_or_none()
                                        if related_obj:
                                            # update provided fields on the related object
                                            for r_key, r_val in item.items():
                                                if r_key == "id":
                                                    continue
                                                if hasattr(related_obj, r_key):
                                                    setattr(related_obj, r_key, r_val)
                                            new_list.append(related_obj)
                                        else:
                                            # Remove audit fields from nested data
                                            cleaned_item = {k: v for k, v in item.items() if k not in AUDIT_FIELDS}
                                            new_item = related_model(**cleaned_item)
                                            session.add(new_item)
                                            new_list.append(new_item)
                                    else:
                                        # Remove audit fields from nested data
                                        cleaned_item = {k: v for k, v in item.items() if k not in AUDIT_FIELDS}
                                        new_item = related_model(**cleaned_item)
                                        session.add(new_item)
                                        new_list.append(new_item)
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