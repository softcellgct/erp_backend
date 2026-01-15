from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class CashCounterBase(BaseModel):
    name: str
    code: str
    is_active: bool = True
    institution_id: UUID

class CashCounterCreate(CashCounterBase):
    pass

class CashCounterUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None

class CashCounterResponse(CashCounterBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
