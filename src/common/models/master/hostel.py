from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON


class Hostel(Base):
    __tablename__ = "hostels"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # relationships
    # rooms and structures will reference this table
