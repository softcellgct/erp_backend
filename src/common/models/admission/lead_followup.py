import enum
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from components.db.base_model import Base

class FollowUpStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"
    NOT_REACHABLE = "Not Reachable"
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    VISIT_SCHEDULED = "Visit Scheduled"

class LeadFollowUp(Base):
    __tablename__ = "lead_followups"

    student_id = Column(UUID(as_uuid=True), ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True)
    remark = Column(Text, nullable=False)
    status = Column(Enum(FollowUpStatusEnum), default=FollowUpStatusEnum.PENDING, nullable=False)
    next_follow_up_date = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True) # Linked to user ID
    
    # Relationship
    student = relationship("AdmissionStudent")

    def __repr__(self):
        return f"<LeadFollowUp(student_id={self.student_id}, status='{self.status}')>"
