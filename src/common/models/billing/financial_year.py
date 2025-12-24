from datetime import date
from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import Date, ForeignKey, String, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FinancialYear(Base):
    __tablename__ = "financial_years"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    fee_structures = relationship("FeeStructure", back_populates="financial_year", lazy="selectin")
    academic_year = relationship("AcademicYear", back_populates="financial_years", lazy="selectin")

    __table_args__ = (
        CheckConstraint("start_date < end_date", name="ck_financial_year_start_lt_end"),
    )

    @classmethod
    async def create(cls, request, session, data_list: list):
        """Override create to enforce single active financial year per institution."""
        from components.generator.utils.get_user_from_request import get_user_id
        from sqlalchemy import update

        if not data_list:
            raise ValueError("No data provided to create records.")

        # Validate only one active per institution in incoming payload
        active_per_inst = {}
        for data in data_list:
            obj = data.dict() if hasattr(data, "dict") else data
            inst = obj.get("institution_id")
            if obj.get("active"):
                if active_per_inst.get(inst):
                    raise ValueError("Multiple active financial years provided for the same institution in request")
                active_per_inst[inst] = True

        user_id = await get_user_id(request)

        # For any institution that has an active in payload, deactivate existing ones first
        for inst in active_per_inst.keys():
            await session.execute(
                update(cls).where(cls.institution_id == inst).values(active=False)
            )

        # Proceed with default create behavior (but set created_by)
        objects = []
        from sqlalchemy.inspection import inspect
        for data in data_list:
            obj_data = data.dict() if hasattr(data, "dict") else data
            obj_data["created_by"] = user_id
            mapper = inspect(cls)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in obj_data and obj_data[rel_name] is not None:
                    rel_data = obj_data[rel_name]
                    if isinstance(rel_data, dict):
                        related_model = rel.mapper.class_
                        obj_data[rel_name] = related_model(**rel_data)
            objects.append(cls(**obj_data))

        session.add_all(objects)
        await session.commit()

        return len(objects)

    @classmethod
    async def update(cls, request, session, data_list: list):
        """Override update to enforce single active financial year when toggling active."""
        from components.generator.utils.get_user_from_request import get_user_id
        from sqlalchemy import update, select

        if not data_list:
            raise ValueError("No data provided for update.")

        user_id = await get_user_id(request)

        # Convert and validate
        obj_ids = []
        updates = []
        for data in data_list:
            data_dict = data.dict(exclude_unset=True) if hasattr(data, "dict") else data
            obj_id = data_dict.get("id")
            if not obj_id:
                raise ValueError("Each object must have an 'id' field.")
            obj_ids.append(obj_id)
            updates.append((obj_id, data_dict))

        # fetch existing
        result = await session.execute(select(cls).where(cls.id.in_(obj_ids), cls.deleted_at.is_(None)))
        existing_objs = result.scalars().all()
        existing_map = {obj.id: obj for obj in existing_objs}

        missing = [oid for oid in obj_ids if oid not in existing_map]
        if missing:
            raise ValueError(f"Records with IDs {missing} not found or deleted.")

        for obj_id, data_dict in updates:
            instance = existing_map[obj_id]
            # If active True is being set, deactivate others for this institution
            if data_dict.get("active") is True:
                await session.execute(
                    update(cls)
                    .where(cls.institution_id == instance.institution_id, cls.id != instance.id)
                    .values(active=False)
                )
            for key, value in data_dict.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            if hasattr(instance, "updated_by"):
                instance.updated_by = user_id

        await session.commit()
        return len(updates)

