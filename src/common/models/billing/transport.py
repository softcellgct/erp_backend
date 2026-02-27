from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON


class TransportRoute(Base):
    __tablename__ = "transport_routes"

    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TransportBus(Base):
    __tablename__ = "transport_buses"

    route_id: Mapped[UUID | None] = mapped_column(ForeignKey("transport_routes.id", ondelete="SET NULL"), nullable=True, index=True)
    bus_number: Mapped[str] = mapped_column(String(50), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TransportFeeStructure(Base):
    __tablename__ = "transport_fee_structures"

    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    batch: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    route_id: Mapped[UUID | None] = mapped_column(ForeignKey("transport_routes.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
