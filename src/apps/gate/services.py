from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from common.models.gate.visitor_model import (
    Visitor,
    VendorVisitor,
    AdmissionVisitor,
    PersonType,
    VisitStatus,
)
from common.schemas.gate.visitor_schemas import (
    VisitorCreate,
    VisitorUpdate,
    VendorVisitorCreate,
    AdmissionVisitorCreate,
    VisitorCheckIn,
    VisitorCheckOut,
)


class VisitorService:
    """Service class for managing visitor operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =====================================================
    # PersonType CRUD Operations
    # =====================================================

    async def create_person_type(self, name: str, description: Optional[str] = None):
        """Create a new person type"""
        person_type = PersonType(name=name, description=description)
        self.db.add(person_type)
        await self.db.commit()
        await self.db.refresh(person_type)
        return person_type

    async def get_person_types(self, active_only: bool = True):
        """Get all person types"""
        query = select(PersonType)
        if active_only:
            query = query.where(PersonType.is_active)
        result = await self.db.execute(query)
        return result.scalars().all()

    # =====================================================
    # General Visitor Operations
    # =====================================================

    async def create_visitor(self, visitor_data: VisitorCreate):
        """Create a new visitor"""
        visitor = Visitor(**visitor_data.model_dump())
        self.db.add(visitor)
        await self.db.commit()
        await self.db.refresh(visitor)
        return visitor

    async def get_visitor(self, visitor_id: UUID):
        """Get a visitor by ID"""
        result = await self.db.execute(
            select(Visitor).where(Visitor.id == visitor_id)
        )
        visitor = result.scalar_one_or_none()
        if not visitor:
            raise HTTPException(status_code=404, detail="Visitor not found")
        return visitor

    async def update_visitor(self, visitor_id: UUID, visitor_data: VisitorUpdate):
        """Update visitor information"""
        visitor = await self.get_visitor(visitor_id)
        
        update_data = visitor_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(visitor, key, value)
        
        await self.db.commit()
        await self.db.refresh(visitor)
        return visitor

    async def get_all_visitors(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[VisitStatus] = None,
    ):
        """Get all visitors with optional filtering"""
        query = select(Visitor).offset(skip).limit(limit)
        
        if status:
            query = query.where(Visitor.visit_status == status)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    # =====================================================
    # Vendor Visitor Operations
    # =====================================================

    async def create_vendor_visitor(self, vendor_data: VendorVisitorCreate):
        """Create a new vendor visitor"""
        # Create base visitor
        visitor = Visitor(**vendor_data.visitor.model_dump())
        self.db.add(visitor)
        await self.db.flush()  # Get visitor ID without committing
        
        # Create vendor-specific details
        vendor = VendorVisitor(
            visitor_id=visitor.id,
            company_name=vendor_data.company_name,
            company_address=vendor_data.company_address,
            company_contact=vendor_data.company_contact,
            designation=vendor_data.designation,
            carrying_materials=vendor_data.carrying_materials,
            material_description=vendor_data.material_description,
        )
        self.db.add(vendor)
        
        await self.db.commit()
        await self.db.refresh(visitor)
        await self.db.refresh(vendor)
        
        return {"visitor": visitor, "vendor_details": vendor}

    # =====================================================
    # Admission Visitor Operations
    # =====================================================

    async def create_admission_visitor(self, admission_data: AdmissionVisitorCreate):
        """Create a new admission visitor"""
        # Create base visitor
        visitor = Visitor(**admission_data.visitor.model_dump())
        self.db.add(visitor)
        await self.db.flush()
        
        # Create admission-specific details
        admission = AdmissionVisitor(
            visitor_id=visitor.id,
            student_name=admission_data.student_name,
            guardian_name=admission_data.guardian_name,
            course_interested=admission_data.course_interested,
            qualification=admission_data.qualification,
            email=admission_data.email,
            has_appointment=admission_data.has_appointment,
            appointment_with=admission_data.appointment_with,
            appointment_time=admission_data.appointment_time,
        )
        self.db.add(admission)
        
        await self.db.commit()
        await self.db.refresh(visitor)
        await self.db.refresh(admission)
        
        return {"visitor": visitor, "admission_details": admission}

    # =====================================================
    # Check-in/Check-out Operations
    # =====================================================

    async def check_in_visitor(self, check_in_data: VisitorCheckIn):
        """Check in a visitor"""
        visitor = await self.get_visitor(check_in_data.visitor_id)
        
        if visitor.visit_status == VisitStatus.CHECKED_IN:
            raise HTTPException(
                status_code=400, detail="Visitor is already checked in"
            )
        
        visitor.visit_status = VisitStatus.CHECKED_IN
        visitor.check_in_time = check_in_data.check_in_time or datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(visitor)
        return visitor

    async def check_out_visitor(self, check_out_data: VisitorCheckOut):
        """Check out a visitor"""
        visitor = await self.get_visitor(check_out_data.visitor_id)
        
        if visitor.visit_status != VisitStatus.CHECKED_IN:
            raise HTTPException(
                status_code=400, detail="Visitor is not checked in"
            )
        
        visitor.visit_status = VisitStatus.CHECKED_OUT
        visitor.check_out_time = check_out_data.check_out_time or datetime.utcnow()
        
        if check_out_data.remarks:
            visitor.remarks = check_out_data.remarks
        
        await self.db.commit()
        await self.db.refresh(visitor)
        return visitor

    # =====================================================
    # Pass Generation
    # =====================================================

    async def generate_pass(self, visitor_id: UUID):
        """Generate a visitor pass"""
        visitor = await self.get_visitor(visitor_id)
        
        if visitor.pass_number:
            raise HTTPException(
                status_code=400, detail="Pass already generated for this visitor"
            )
        
        # Generate unique pass number
        pass_number = f"VP{datetime.now().strftime('%Y%m%d')}{str(uuid4())[:8].upper()}"
        
        visitor.pass_number = pass_number
        visitor.pass_generated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(visitor)
        return visitor

    # =====================================================
    # Statistics and Reports
    # =====================================================

    async def get_today_visitors_count(self):
        """Get count of today's visitors"""
        from sqlalchemy import func
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await self.db.execute(
            select(func.count(Visitor.id)).where(
                Visitor.created_at >= today_start
            )
        )
        return result.scalar()

    async def get_active_visitors(self):
        """Get all currently checked-in visitors"""
        result = await self.db.execute(
            select(Visitor).where(Visitor.visit_status == VisitStatus.CHECKED_IN)
        )
        return result.scalars().all()
