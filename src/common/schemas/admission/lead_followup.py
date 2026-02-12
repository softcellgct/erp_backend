from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from enum import Enum

class FollowUpStatusEnum(str, Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"
    NOT_REACHABLE = "Not Reachable"
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    VISIT_SCHEDULED = "Visit Scheduled"

class LeadFollowUpBase(BaseModel):
    student_id: UUID
    remark: str
    status: FollowUpStatusEnum = FollowUpStatusEnum.PENDING
    next_follow_up_date: Optional[datetime] = None

class LeadFollowUpCreate(LeadFollowUpBase):
    pass

class LeadFollowUpUpdate(BaseModel):
    remark: Optional[str] = None
    status: Optional[FollowUpStatusEnum] = None
    next_follow_up_date: Optional[datetime] = None

class LeadFollowUpResponse(LeadFollowUpBase):
    id: UUID
    created_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True
