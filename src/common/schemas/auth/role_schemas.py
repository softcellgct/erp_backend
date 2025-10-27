from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class RoleCreateSchema(BaseModel):
    name: str
    description: str

class RoleUpdateSchema(BaseModel):
    id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None

class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str
