from pydantic import BaseModel
from uuid import UUID
from typing import Optional

# Module Schemas
class ModuleBase(BaseModel):
    name: str
    title: str
    module_img_url: Optional[str] = None
    is_active: bool = True

class ModuleCreate(ModuleBase):
    pass

class ModuleUpdate(BaseModel):
    id:UUID
    name: Optional[str] = None
    title: Optional[str] = None
    module_img_url: Optional[str] = None
    is_active: Optional[bool] = None

class ModuleResponse(ModuleBase):
    id: UUID

    class Config:
        from_attributes = True


# Screen Schemas
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
