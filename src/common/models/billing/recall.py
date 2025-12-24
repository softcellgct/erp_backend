from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON


class PaymentRecallRequest(Base):
    __tablename__ = "payment_recall_requests"

    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="requested")
    processed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
