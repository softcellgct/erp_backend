from pydantic import BaseModel, ConfigDict
from datetime import datetime, date, time
from typing import Optional
from uuid import UUID
from enum import Enum

class MaterialStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    RETURNED = "returned"

class MaterialPassBase(BaseModel):
    name: str
    material_name: str
    quantity: int
    out_time: time
    out_date: date
    company_name: str
    place: str
    description: Optional[str] = None
    has_vehicle: bool = False
    vehicle_number: Optional[str] = None
    vehicle_name: Optional[str] = None
    pending_quantity: Optional[int] = None

class MaterialPassCreate(MaterialPassBase):
    pass

class MaterialPassUpdate(BaseModel):
    in_quantity: Optional[int] = None
    status: Optional[MaterialStatus] = None
    description: Optional[str] = None
    in_date: Optional[date] = None
    in_time: Optional[time] = None

class MaterialPassResponse(MaterialPassBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    pass_number: str
    in_quantity: int
    status: MaterialStatus
    in_date: Optional[date] = None
    in_time: Optional[time] = None
    created_at: datetime
    updated_at: datetime

class MaterialInBase(BaseModel):
    staff_name: str
    material_name: str
    quantity: int
    bill_number: str
    bill_date: date
    total_amount: str
    company_name: str
    has_vehicle: bool = False
    vehicle_number: Optional[str] = None
    vehicle_charge: Optional[str] = None

class MaterialInCreate(MaterialInBase):
    pass

class MaterialInResponse(MaterialInBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    pass_number: str
    created_at: datetime
    updated_at: datetime

class UnifiedMaterialReportItem(BaseModel):
    id: UUID
    pass_number: str
    pass_type: str # "Material Out/In" or "New Material"
    name: str # staff_name or name
    material_name: str
    quantity: int
    company_name: str
    place_or_bill: str # place or bill_number
    date: date # out_date or bill_date
    time: Optional[str] = None # out_time or created_at time
    status: str # "active", "pending", "returned" or "received"
    in_date: Optional[date] = None
    in_time: Optional[time] = None
    in_quantity: Optional[int] = None
    pending_quantity: Optional[int] = None
    vehicle_number: Optional[str] = None
    vehicle_name: Optional[str] = None
    created_at: datetime
