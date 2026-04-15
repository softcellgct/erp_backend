"""
Service for scholarship configuration and staff referral concession management.
Handles CRUD operations and business logic for both scholarship configs and referral concessions.
"""
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.models.billing.scholarship_config import (
    ScholarshipConfiguration,
    StaffReferralConcession,
    ScholarshipTypeConfigEnum,
)
from common.models.admission.admission_entry import AdmissionStudent
from common.models.master.user import User
from common.models.billing.application_fees import FeeHead
from common.schemas.billing.scholarship_config_schemas import (
    ScholarshipConfigurationCreate,
    ScholarshipConfigurationUpdate,
    ScholarshipConfigurationResponse,
    StaffReferralConcessionCreate,
    StaffReferralConcessionUpdate,
    StaffReferralConcessionResponse,
)
from logs.logging import logger


class ScholarshipConfigurationService:
    """Service for managing scholarship configurations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        data: ScholarshipConfigurationCreate,
    ) -> ScholarshipConfiguration:
        """Create a new scholarship configuration."""
        config = ScholarshipConfiguration(
            institution_id=data.institution_id,
            scholarship_type=ScholarshipTypeConfigEnum(data.scholarship_type),
            amount=data.amount,
            percentage=data.percentage,
            fee_head_id=data.fee_head_id,
            description=data.description,
            is_active=data.is_active,
            reduce_from_tuition=data.reduce_from_tuition,
            meta=data.meta or {},
        )
        db.add(config)
        await db.flush()
        return config

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        config_id: UUID,
    ) -> ScholarshipConfiguration | None:
        """Fetch a scholarship configuration by ID."""
        stmt = select(ScholarshipConfiguration).where(
            ScholarshipConfiguration.id == config_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_institution_and_type(
        db: AsyncSession,
        institution_id: UUID,
        scholarship_type: str,
    ) -> ScholarshipConfiguration | None:
        """Fetch configuration for a specific institution and scholarship type."""
        stmt = select(ScholarshipConfiguration).where(
            and_(
                ScholarshipConfiguration.institution_id == institution_id,
                ScholarshipConfiguration.scholarship_type == ScholarshipTypeConfigEnum(scholarship_type),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_by_institution(
        db: AsyncSession,
        institution_id: UUID,
        is_active: bool | None = None,
    ) -> list[ScholarshipConfiguration]:
        """List all scholarship configurations for an institution."""
        conditions = [ScholarshipConfiguration.institution_id == institution_id]
        if is_active is not None:
            conditions.append(ScholarshipConfiguration.is_active == is_active)

        stmt = select(ScholarshipConfiguration).where(and_(*conditions))
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update(
        db: AsyncSession,
        config_id: UUID,
        data: ScholarshipConfigurationUpdate,
    ) -> ScholarshipConfiguration | None:
        """Update a scholarship configuration."""
        config = await ScholarshipConfigurationService.get_by_id(db, config_id)
        if not config:
            return None

        if data.amount is not None:
            config.amount = data.amount
        if data.percentage is not None:
            config.percentage = data.percentage
        if data.fee_head_id is not None:
            config.fee_head_id = data.fee_head_id
        if data.description is not None:
            config.description = data.description
        if data.is_active is not None:
            config.is_active = data.is_active
        if data.reduce_from_tuition is not None:
            config.reduce_from_tuition = data.reduce_from_tuition
        if data.meta is not None:
            config.meta = data.meta

        await db.flush()
        return config

    @staticmethod
    async def delete(
        db: AsyncSession,
        config_id: UUID,
    ) -> bool:
        """Delete a scholarship configuration."""
        config = await ScholarshipConfigurationService.get_by_id(db, config_id)
        if not config:
            return False

        await db.delete(config)
        await db.flush()
        return True


class StaffReferralConcessionService:
    """Service for managing staff referral concessions."""

    @staticmethod
    async def create(
        db: AsyncSession,
        data: StaffReferralConcessionCreate,
    ) -> StaffReferralConcession:
        """Create a new staff referral concession."""
        # Get scholarship config for STAFF_REFERRAL to calculate amount if needed
        if data.concession_amount is None and data.concession_percentage is None:
            config = await ScholarshipConfigurationService.get_by_institution_and_type(
                db,
                data.institution_id,
                "STAFF_REFERRAL",
            )
            if config:
                if config.amount:
                    data.concession_amount = config.amount
                elif config.percentage:
                    data.concession_percentage = config.percentage

        concession = StaffReferralConcession(
            staff_id=data.staff_id,
            student_id=data.student_id,
            institution_id=data.institution_id,
            concession_amount=data.concession_amount or Decimal("0"),
            concession_percentage=data.concession_percentage,
            fee_head_id=data.fee_head_id,
            notes=data.notes,
            meta=data.meta or {},
        )
        db.add(concession)
        await db.flush()
        logger.info(f"Created staff referral concession: {concession.id}")
        return concession

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        concession_id: UUID,
    ) -> StaffReferralConcession | None:
        """Fetch a staff referral concession by ID."""
        stmt = select(StaffReferralConcession).where(
            StaffReferralConcession.id == concession_id
        ).options(
            selectinload(StaffReferralConcession.staff),
            selectinload(StaffReferralConcession.student),
            selectinload(StaffReferralConcession.fee_head),
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_by_staff(
        db: AsyncSession,
        staff_id: UUID,
        is_applied: bool | None = None,
    ) -> list[StaffReferralConcession]:
        """List all concessions created by a specific staff member."""
        conditions = [StaffReferralConcession.staff_id == staff_id]
        if is_applied is not None:
            conditions.append(StaffReferralConcession.is_applied == is_applied)

        stmt = select(StaffReferralConcession).where(and_(*conditions)).options(
            selectinload(StaffReferralConcession.student),
            selectinload(StaffReferralConcession.fee_head),
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_by_student(
        db: AsyncSession,
        student_id: UUID,
    ) -> list[StaffReferralConcession]:
        """List all concessions for a specific student."""
        stmt = select(StaffReferralConcession).where(
            StaffReferralConcession.student_id == student_id
        ).options(
            selectinload(StaffReferralConcession.staff),
            selectinload(StaffReferralConcession.fee_head),
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_by_institution(
        db: AsyncSession,
        institution_id: UUID,
        is_applied: bool | None = None,
    ) -> list[StaffReferralConcession]:
        """List all staff referral concessions for an institution."""
        conditions = [StaffReferralConcession.institution_id == institution_id]
        if is_applied is not None:
            conditions.append(StaffReferralConcession.is_applied == is_applied)

        stmt = select(StaffReferralConcession).where(and_(*conditions)).options(
            selectinload(StaffReferralConcession.staff),
            selectinload(StaffReferralConcession.student),
            selectinload(StaffReferralConcession.fee_head),
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update(
        db: AsyncSession,
        concession_id: UUID,
        data: StaffReferralConcessionUpdate,
    ) -> StaffReferralConcession | None:
        """Update a staff referral concession."""
        concession = await StaffReferralConcessionService.get_by_id(db, concession_id)
        if not concession:
            return None

        if data.concession_amount is not None:
            concession.concession_amount = data.concession_amount
        if data.concession_percentage is not None:
            concession.concession_percentage = data.concession_percentage
        if data.fee_head_id is not None:
            concession.fee_head_id = data.fee_head_id
        if data.is_applied is not None:
            concession.is_applied = data.is_applied
            if data.is_applied:
                concession.applied_at = datetime.now(timezone.utc).isoformat()
        if data.applied_at is not None:
            concession.applied_at = data.applied_at
        if data.notes is not None:
            concession.notes = data.notes
        if data.meta is not None:
            concession.meta = data.meta

        await db.flush()
        logger.info(f"Updated staff referral concession: {concession_id}")
        return concession

    @staticmethod
    async def delete(
        db: AsyncSession,
        concession_id: UUID,
    ) -> bool:
        """Delete a staff referral concession."""
        concession = await StaffReferralConcessionService.get_by_id(db, concession_id)
        if not concession:
            return False

        await db.delete(concession)
        await db.flush()
        logger.info(f"Deleted staff referral concession: {concession_id}")
        return True

    @staticmethod
    async def apply_to_invoice(
        db: AsyncSession,
        concession_id: UUID,
    ) -> bool:
        """Mark a concession as applied to an invoice."""
        concession = await StaffReferralConcessionService.get_by_id(db, concession_id)
        if not concession:
            return False

        concession.is_applied = True
        concession.applied_at = datetime.now(timezone.utc).isoformat()
        await db.flush()
        logger.info(f"Applied staff referral concession to invoice: {concession_id}")
        return True
