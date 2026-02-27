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

    # student_id can reference either admission_students.id OR admission_visitors.id
    # No FK constraint to allow flexibility
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    remark = Column(Text, nullable=False)
    status = Column(Enum(FollowUpStatusEnum), default=FollowUpStatusEnum.PENDING, nullable=False)
    next_follow_up_date = Column(DateTime, nullable=True)
    # created_by inherited from Base with FK to users.id

    def __repr__(self):
        return f"<LeadFollowUp(student_id={self.student_id}, status='{self.status}')>"

    @classmethod
    async def create(cls, request, session, data_list):
        """Create follow-up records for students."""
        from sqlalchemy import select
        from common.models.admission.admission_entry import AdmissionStudent

        if not data_list:
            raise ValueError("No data provided to create records.")

        # Validate that all student_ids exist in admission_students
        for item in data_list:
            payload = item.dict(exclude_unset=True) if hasattr(item, "dict") else dict(item)
            sid = payload.get("student_id")

            if not sid:
                raise ValueError("LeadFollowUp item must include 'student_id'.")

            stmt = select(AdmissionStudent).where(AdmissionStudent.id == sid)
            res = await session.execute(stmt)
            student = res.scalars().one_or_none()

            if not student:
                raise ValueError(f"student_id {sid} not found in admission_students")

        # All IDs validated, proceed with creation
        return await super().create(request, session, data_list)
