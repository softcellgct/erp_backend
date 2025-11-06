from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class CommunityBase(BaseModel):
    name: str = Field(..., max_length=100)


class CommunityCreate(CommunityBase):
    pass


class CommunityUpdate(BaseModel):
    id: UUID
    name: Optional[str] = Field(None, max_length=100)


class CasteResponse(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True

class CommunityResponse(CommunityBase):
    id: UUID
    castes: Optional[list[CasteResponse]] = None

    class Config:
        from_attributes = True
