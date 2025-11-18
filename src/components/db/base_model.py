import uuid
from typing import Any, List, Optional

from fastapi import Request
from sqlalchemy import UUID, DateTime, ForeignKey, delete, func, select, update
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

@as_declarative()
class Base:  # noqa: F811
    """
    =====================================================
    # Base model to include default columns for all tables.
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
        DateTime(timezone=True), nullable=True
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )  # Track the creator
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )  # Track the updater
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )  # Soft delete column


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

        objects = []
        for data in data_list:
            user_id = await get_user_id(request)
            obj_data = data.dict() if hasattr(data, "dict") else data
            obj_data["created_by"] = user_id
            
            # Handle nested relationships - convert dict to model instances
            mapper = inspect(cls)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in obj_data and obj_data[rel_name] is not None:
                    rel_data = obj_data[rel_name]
                    if isinstance(rel_data, dict):
                        # Get the related model class
                        related_model = rel.mapper.class_
                        # Create instance of related model
                        obj_data[rel_name] = related_model(**rel_data)
            
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

            for key, value in data.items():
                if hasattr(instance, key):
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