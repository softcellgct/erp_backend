from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class HostelFeeStructureBase(BaseModel):
    college_id: UUID
    hostel_id: Optional[UUID] = None
    room_type: str
    ac: Optional[bool] = False
    financial_year_id: Optional[UUID] = None
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Decimal
    installments: Optional[dict] = None
    status: Optional[bool] = True
    meta: Optional[dict] = None


class HostelFeeStructureCreate(HostelFeeStructureBase):
    pass


class HostelFeeStructureUpdate(BaseModel):
    id: UUID
    room_type: Optional[str] = None
    ac: Optional[bool] = None
    financial_year_id: Optional[UUID] = None
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Optional[Decimal] = None
    installments: Optional[dict] = None
    status: Optional[bool] = None
    meta: Optional[dict] = None


class HostelFeeStructureResponse(HostelFeeStructureBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HostelRoomBase(BaseModel):
    hostel_id: Optional[UUID] = None
    room_no: str
    room_type: Optional[str] = None
    capacity: Optional[int] = 1
    ac: Optional[bool] = False
    meta: Optional[dict] = None


class HostelRoomCreate(HostelRoomBase):
    pass


class HostelRoomResponse(HostelRoomBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
