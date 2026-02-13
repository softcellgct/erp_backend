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
    created_by = Column(UUID(as_uuid=True), nullable=True) # Linked to user ID

    def __repr__(self):
        return f"<LeadFollowUp(student_id={self.student_id}, status='{self.status}')>"

    @classmethod
    async def create(cls, request, session, data_list):
        """Create follow-up records for visitors or students."""
        from sqlalchemy import select
        from common.models.gate.visitor_model import AdmissionVisitor
        from common.models.admission.admission_entry import AdmissionStudent

        if not data_list:
            raise ValueError("No data provided to create records.")

        # Validate that all student_ids exist in either table
        for item in data_list:
            payload = item.dict(exclude_unset=True) if hasattr(item, "dict") else dict(item)
            sid = payload.get("student_id")

            if not sid:
                raise ValueError("LeadFollowUp item must include 'student_id'.")

            # Check if ID exists in AdmissionStudent
            stmt_student = select(AdmissionStudent).where(AdmissionStudent.id == sid)
            res_student = await session.execute(stmt_student)
            student = res_student.scalars().one_or_none()

            if student:
                continue  # Valid student ID

            # Check if ID exists in AdmissionVisitor
            stmt_visitor = select(AdmissionVisitor).where(AdmissionVisitor.id == sid)
            res_visitor = await session.execute(stmt_visitor)
            visitor = res_visitor.scalars().one_or_none()

            if not visitor:
                raise ValueError(f"student_id {sid} not found in admission_students or admission_visitors")

        # All IDs validated, proceed with creation
        return await super().create(request, session, data_list)
