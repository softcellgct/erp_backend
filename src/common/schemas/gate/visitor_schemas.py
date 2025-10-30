from pydantic import BaseModel, Field, validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class VisitorTypeEnum(str, Enum):
    """Enum for visitor types"""
    GENERAL = "general"
    VENDOR = "vendor"
    ADMISSION = "admission"


class VisitStatusEnum(str, Enum):
    """Enum for visit status"""
    PENDING = "pending"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


# =====================================================
# PersonType Schemas
# =====================================================

class PersonTypeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class PersonTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class PersonTypeResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# Visitor Schemas
# =====================================================

class VisitorCreate(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the visitor")
    contact_number: str = Field(..., max_length=20, description="Contact number")
    members_count: int = Field(1, ge=1, description="Number of members in the group")
    visitor_type: VisitorTypeEnum = Field(
        VisitorTypeEnum.GENERAL, description="Type of visitor"
    )
    
    institution_id: UUID = Field(..., description="Institution ID")
    department_id: UUID = Field(..., description="Department ID")
    person_type_id: UUID = Field(..., description="Person type ID")
    person_name: str = Field(..., max_length=255, description="Name of person to meet")
    
    purpose_of_visit: str = Field(..., description="Purpose of the visit")
    
    has_vehicle: bool = Field(False, description="Does visitor have a vehicle?")
    vehicle_number: Optional[str] = Field(None, max_length=50)
    vehicle_type: Optional[str] = Field(None, max_length=50)
    
    photo_url: Optional[str] = Field(None, max_length=500)
    
    remarks: Optional[str] = None

    @validator('contact_number')
    def validate_contact(cls, v):
        if not v.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError('Contact number must contain only digits, +, -, and spaces')
        return v


class VisitorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    contact_number: Optional[str] = Field(None, max_length=20)
    members_count: Optional[int] = Field(None, ge=1)
    visitor_type: Optional[VisitorTypeEnum] = None
    
    institution_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    person_type_id: Optional[UUID] = None
    person_name: Optional[str] = Field(None, max_length=255)
    
    purpose_of_visit: Optional[str] = None
    
    has_vehicle: Optional[bool] = None
    vehicle_number: Optional[str] = Field(None, max_length=50)
    vehicle_type: Optional[str] = Field(None, max_length=50)
    
    photo_url: Optional[str] = Field(None, max_length=500)
    
    visit_status: Optional[VisitStatusEnum] = None
    remarks: Optional[str] = None


class VisitorResponse(BaseModel):
    id: UUID
    name: str
    contact_number: str
    members_count: int
    visitor_type: VisitorTypeEnum
    
    institution_id: UUID
    department_id: UUID
    person_type_id: UUID
    person_name: str
    
    purpose_of_visit: str
    
    has_vehicle: bool
    vehicle_number: Optional[str]
    vehicle_type: Optional[str]
    
    photo_url: Optional[str]
    
    pass_number: Optional[str]
    pass_generated_at: Optional[datetime]
    
    visit_status: VisitStatusEnum
    check_in_time: Optional[datetime]
    check_out_time: Optional[datetime]
    
    remarks: Optional[str]
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# VendorVisitor Schemas
# =====================================================

class VendorVisitorCreate(BaseModel):
    # Base visitor info
    visitor: VisitorCreate
    
    # Vendor-specific info
    company_name: str = Field(..., max_length=255)
    company_address: Optional[str] = None
    company_contact: Optional[str] = Field(None, max_length=20)
    designation: Optional[str] = Field(None, max_length=100)
    
    carrying_materials: bool = False
    material_description: Optional[str] = None


class VendorVisitorUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    company_address: Optional[str] = None
    company_contact: Optional[str] = Field(None, max_length=20)
    designation: Optional[str] = Field(None, max_length=100)
    
    carrying_materials: Optional[bool] = None
    material_description: Optional[str] = None


class VendorVisitorResponse(BaseModel):
    id: UUID
    visitor_id: UUID
    company_name: str
    company_address: Optional[str]
    company_contact: Optional[str]
    designation: Optional[str]
    carrying_materials: bool
    material_description: Optional[str]
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# AdmissionVisitor Schemas
# =====================================================

class AdmissionVisitorCreate(BaseModel):
    # Base visitor info
    visitor: VisitorCreate
    
    # Admission-specific info
    student_name: str = Field(..., max_length=255)
    guardian_name: Optional[str] = Field(None, max_length=255)
    course_interested: Optional[str] = Field(None, max_length=255)
    qualification: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    
    has_appointment: bool = False
    appointment_with: Optional[str] = Field(None, max_length=255)
    appointment_time: Optional[datetime] = None


class AdmissionVisitorUpdate(BaseModel):
    student_name: Optional[str] = Field(None, max_length=255)
    guardian_name: Optional[str] = Field(None, max_length=255)
    course_interested: Optional[str] = Field(None, max_length=255)
    qualification: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    
    has_appointment: Optional[bool] = None
    appointment_with: Optional[str] = Field(None, max_length=255)
    appointment_time: Optional[datetime] = None


class AdmissionVisitorResponse(BaseModel):
    id: UUID
    visitor_id: UUID
    student_name: str
    guardian_name: Optional[str]
    course_interested: Optional[str]
    qualification: Optional[str]
    email: Optional[str]
    has_appointment: bool
    appointment_with: Optional[str]
    appointment_time: Optional[datetime]
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# Check-in/Check-out Schemas
# =====================================================

class VisitorCheckIn(BaseModel):
    visitor_id: UUID
    check_in_time: Optional[datetime] = None  # If None, use current time


class VisitorCheckOut(BaseModel):
    visitor_id: UUID
    check_out_time: Optional[datetime] = None  # If None, use current time
    remarks: Optional[str] = None


# =====================================================
# Pass Generation Schema
# =====================================================

class GeneratePassRequest(BaseModel):
    visitor_id: UUID


class GeneratePassResponse(BaseModel):
    visitor_id: UUID
    pass_number: str
    pass_generated_at: datetime
    photo_url: Optional[str]
    name: str
    purpose: str
    person_to_meet: str
    department: str

    class Config:
        from_attributes = True
