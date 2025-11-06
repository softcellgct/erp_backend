from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class ReligionBase(BaseModel):
    name: str = Field(..., max_length=100)


class ReligionCreate(ReligionBase):
    pass


class ReligionUpdate(BaseModel):
    id: UUID
    name: Optional[str] = Field(None, max_length=100)


class ReligionResponse(ReligionBase):
    id: UUID

    class Config:
        from_attributes = True
