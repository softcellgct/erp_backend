from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Text,
    Enum as SQLEnum,
    func,
    Integer,
    Date,
    Time
)
from components.db.base_model import Base
from datetime import datetime, date, time
import enum

class MaterialStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    RETURNED = "returned"

class MaterialPass(Base):
    __tablename__ = "material_passes"

    pass_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[str] = mapped_column(String(100), nullable=False)
    in_quantity: Mapped[str] = mapped_column(String(100), default="0", nullable=False)
    pending_quantity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    out_date: Mapped[date] = mapped_column(Date, default=func.current_date(), nullable=False)
    out_time: Mapped[time] = mapped_column(Time, nullable=False)
    
    in_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    in_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    place: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    status: Mapped[MaterialStatus] = mapped_column(
        SQLEnum(MaterialStatus, native_enum=False),
        nullable=False,
        default=MaterialStatus.ACTIVE
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class MaterialIn(Base):
    __tablename__ = "material_in_entries"

    pass_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    staff_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[str] = mapped_column(String(100), nullable=False)
    bill_number: Mapped[str] = mapped_column(String(255), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[str] = mapped_column(String(50), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_charge: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

