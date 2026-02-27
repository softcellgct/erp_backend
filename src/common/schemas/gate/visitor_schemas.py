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




