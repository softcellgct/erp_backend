from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class ModuleBase(BaseModel):
    name: str
    title: str
    module_img_url: Optional[str] = None
    is_active: bool = True

class ModuleCreate(ModuleBase):
    pass

class ModuleUpdate(BaseModel):
    id:UUID
    title: Optional[str] = None
    module_img_url: Optional[str] = None
    is_active: Optional[bool] = None

class ModuleResponse(ModuleBase):
    id: UUID

    class Config:
        from_attributes = True