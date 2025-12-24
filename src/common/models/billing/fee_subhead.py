from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FeeSubHead(Base):
    __tablename__ = "fee_sub_heads"

    fee_head_id: Mapped[UUID] = mapped_column(ForeignKey("fee_heads.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    batch: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    fee_head = relationship("FeeHead", lazy="selectin")
    structure_items = relationship("FeeStructureItem", back_populates="fee_sub_head", lazy="selectin")
    academic_year = relationship("AcademicYear", lazy="selectin")
