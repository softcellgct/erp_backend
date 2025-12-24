from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON


class Concession(Base):
    __tablename__ = "concessions"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True)
    college_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proof_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ConcessionAudit(Base):
    __tablename__ = "concession_audits"

    concession_id: Mapped[UUID] = mapped_column(ForeignKey("concessions.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
