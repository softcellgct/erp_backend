from components.db.base_model import Base
from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship

class AdmissionType(Base):
    """
    Admission Type Master (e.g., General, Management, Lateral Entry)
    """
    __tablename__ = "admission_types"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AdmissionType(name='{self.name}')>"


class SeatQuota(Base):
    """
    Seat Quota Master (e.g., Sports Quota, Merit Quota)
    """
    __tablename__ = "seat_quotas"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SeatQuota(name='{self.name}')>"


class DocumentType(Base):
    """
    Document Type Master (e.g., Transfer Certificate, Marksheet, Community Certificate)
    """
    __tablename__ = "document_types"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True)
    is_mandatory = Column(Boolean, default=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DocumentType(name='{self.name}')>"
