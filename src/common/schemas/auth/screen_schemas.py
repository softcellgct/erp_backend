from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class ScreenBase(BaseModel):
    name: str
    title: str
    module_id: UUID
    parent_id: Optional[UUID] = None
    is_active: bool = True

class ScreenCreate(ScreenBase):
    pass

class ScreenUpdate(BaseModel):
    id: UUID
    title: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class ScreenResponse(ScreenBase):
    id: UUID

    model_config = {"from_attributes": True}