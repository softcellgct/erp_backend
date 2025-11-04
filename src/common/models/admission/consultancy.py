import enum
from components.db.base_model import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

class ProofType(str, enum.Enum):
    """Enum for proof types"""
    AADHAR = "aadhar"
    VISITING_CARD = "visiting_card"
    OTHER = "other"



class Consultancy(Base):
    """
    Model to store consultancy information for visitors
    """
    __tablename__ = "consultancies"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    proof_type: Mapped[ProofType] = mapped_column(
        SQLEnum(ProofType, native_enum=False),
        nullable=False
    )
    contact_person_proof_number: Mapped[str] = mapped_column(String, nullable=False)
    contact_person_proof_url: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
