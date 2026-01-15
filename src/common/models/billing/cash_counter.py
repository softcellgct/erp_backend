from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class CashCounter(Base):
    __tablename__ = "cash_counters"

    institution_id: Mapped[UUID] = mapped_column(
        # ForeignKey("institutions.id", ondelete="CASCADE"), 
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    # payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="cash_counter")

    def __repr__(self):
        return f"<CashCounter(id={self.id}, name='{self.name}', code='{self.code}')>"
