from uuid import UUID
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from components.db.base_model import Base

class ConcessionRule(Base):
    __tablename__ = "concession_rules"

    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_metric: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'cutoff_marks'
    operator: Mapped[str] = mapped_column(String(10), nullable=False)  # '>', '>=', '==', '<', '<='
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    concession_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
