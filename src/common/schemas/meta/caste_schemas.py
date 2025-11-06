from common.schemas.meta.community_schemas import CommunityResponse
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class CasteBase(BaseModel):
    name: str = Field(..., max_length=100)
    community_id: UUID


class CasteCreate(CasteBase):
    pass


class CasteUpdate(BaseModel):
    id: UUID
    name: Optional[str] = Field(None, max_length=100)
    community_id: Optional[UUID] = None


class CasteResponse(CasteBase):
    id: UUID
    name: str
    community: Optional[CommunityResponse] = None


    class Config:
        from_attributes = True
