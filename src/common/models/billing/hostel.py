from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON


class HostelFeeStructure(Base):
    __tablename__ = "hostel_fee_structures"

    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("hostels.id", ondelete="SET NULL"), nullable=True, index=True)
    room_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ac: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    financial_year_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_years.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    installments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # relationships — lazy="select" to avoid loading related records eagerly
    financial_year = relationship("FinancialYear", lazy="select")
    fee_head = relationship("FeeHead", lazy="select")
    fee_sub_head = relationship("FeeSubHead", lazy="select")


class HostelRoom(Base):
    __tablename__ = "hostel_rooms"

    hostel_id: Mapped[UUID | None] = mapped_column(ForeignKey("hostels.id", ondelete="CASCADE"), nullable=True, index=True)
    room_no: Mapped[str] = mapped_column(String(50), nullable=False)
    room_type: Mapped[str] = mapped_column(String(100), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    ac: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
