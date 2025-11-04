# crud/crud_admission_visitor.py

from re import S
from uuid import UUID
from common.models.gate.visitor_model import (
    AdmissionVisitor,
    ConsultancyReference,
    OtherReference,
    ReferenceType,
    StaffReference,
    StudentReference,
)
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorCreate,
    AdmissionVisitorUpdate,
)
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import joinedload,selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError


class AdmissionVisitorCRUD:
    # -----------------------------------
    # CREATE
    # -----------------------------------
    async def create(self, db: AsyncSession, payload: AdmissionVisitorCreate):
        try:
            data = payload.dict(exclude_unset=True)
            ref_type_raw = data.pop("reference_type")

            # Normalize incoming reference type to ReferenceType enum
            if isinstance(ref_type_raw, str):
                try:
                    # Accept either enum member name (e.g. "CONSULTANCY") or value (e.g. "consultancy")
                    try:
                        ref_type = ReferenceType[ref_type_raw.upper()]
                    except KeyError:
                        ref_type = ReferenceType(ref_type_raw)
                except Exception:
                    # fallback: raise a clear error
                    raise ValueError(f"Invalid reference_type: {ref_type_raw}")
            else:
                ref_type = ref_type_raw

            consultancy = data.pop("consultancy_reference", None)
            if consultancy:
                consultancy = consultancy

            staff = data.pop("staff_reference", None)
            if staff:
                staff = staff

            student = data.pop("student_reference", None)
            if student:
                student = student

            other = data.pop("other_reference", None)
            if other:
                other = other

            # create visitor with enum value
            visitor = AdmissionVisitor(**data, reference_type=ref_type)
            db.add(visitor)
            await db.flush()

            match ref_type:
                case ReferenceType.CONSULTANCY if consultancy:
                    db.add(
                        ConsultancyReference(admission_visitor_id=visitor.id, **consultancy)
                    )
                case ReferenceType.STAFF if staff:
                    db.add(StaffReference(reference_id=visitor.id, **staff))
                case ReferenceType.STUDENT if student:
                    db.add(StudentReference(reference_id=visitor.id, **student))
                case ReferenceType.OTHER if other:
                    db.add(OtherReference(reference_id=visitor.id, **other))

            await db.commit()

            # ✅ Re-fetch with relationships to avoid greenlet error
            stmt = (
                select(AdmissionVisitor)
                .where(AdmissionVisitor.id == visitor.id)
                .options(
                    selectinload(AdmissionVisitor.consultancy_reference),
                    selectinload(AdmissionVisitor.staff_reference),
                    selectinload(AdmissionVisitor.student_reference),
                    selectinload(AdmissionVisitor.other_reference),
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            await db.rollback()
            raise e

        except SQLAlchemyError as e:
            await db.rollback()
            raise e

    # -----------------------------------
    # GET ONE
    # -----------------------------------
    async def get_one(self, db: AsyncSession, visitor_id: UUID):
        stmt = (
            select(AdmissionVisitor)
            .where(AdmissionVisitor.id == visitor_id)
            .options(
                joinedload(AdmissionVisitor.consultancy_reference),
                joinedload(AdmissionVisitor.staff_reference),
                joinedload(AdmissionVisitor.student_reference),
                joinedload(AdmissionVisitor.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    # -----------------------------------
    # GET ALL
    # -----------------------------------
    async def get_all(self, db: AsyncSession, query):
        stmt = query
        result = await paginate(db, stmt)
        return result

    # -----------------------------------
    # UPDATE
    # -----------------------------------
    async def update(
        self, db: AsyncSession, visitor_id: UUID, payload: AdmissionVisitorUpdate
    ):
        visitor = await db.get(AdmissionVisitor, visitor_id)
        if not visitor:
            return None

        for field, value in payload.dict(exclude_unset=True).items():
            setattr(visitor, field, value)

        await db.commit()
        await db.refresh(visitor)
        return visitor

    # -----------------------------------
    # DELETE
    # -----------------------------------
    async def delete(self, db: AsyncSession, visitor_id: UUID):
        visitor = await db.get(AdmissionVisitor, visitor_id)
        if not visitor:
            return 0
        await db.delete(visitor)
        await db.commit()
        return 1


admission_crud = AdmissionVisitorCRUD()
