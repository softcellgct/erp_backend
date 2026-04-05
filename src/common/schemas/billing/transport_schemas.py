from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class TransportRouteBase(BaseModel):
    college_id: UUID
    name: str
    code: Optional[str] = None
    is_active: Optional[bool] = True
    meta: Optional[dict] = None


class TransportRouteCreate(TransportRouteBase):
    pass


class TransportRouteResponse(TransportRouteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransportBusBase(BaseModel):
    route_id: Optional[UUID] = None
    bus_number: str
    seats: Optional[int] = 0
    meta: Optional[dict] = None


class TransportBusCreate(TransportBusBase):
    pass


class TransportBusResponse(TransportBusBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransportFeeStructureBase(BaseModel):
    college_id: UUID
    batch: Optional[str] = None
    route_id: Optional[UUID] = None
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Decimal
    status: Optional[bool] = True
    meta: Optional[dict] = None


class TransportFeeStructureCreate(TransportFeeStructureBase):
    pass


class TransportFeeStructureUpdate(BaseModel):
    id: UUID
    batch: Optional[str] = None
    route_id: Optional[UUID] = None
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Optional[Decimal] = None
    status: Optional[bool] = None
    meta: Optional[dict] = None


class TransportFeeStructureResponse(TransportFeeStructureBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
