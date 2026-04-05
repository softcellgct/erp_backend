from components.db.base_model import Base
from sqlalchemy import Column, String, Boolean, Integer

class AdmissionType(Base):
    """
    Admission Type Master (e.g., General, Management, Lateral Entry)
    """
    __tablename__ = "admission_types"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    # created_at / updated_at inherited from Base with server_default=func.now()

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

    def __repr__(self):
        return f"<SeatQuota(name='{self.name}')>"


class DocumentType(Base):
    """
    Document Type Master (e.g., Transfer Certificate, Marksheet, Community Certificate)
    Also serves as the required certificates configuration for admission.
    """
    __tablename__ = "document_types"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True)
    is_mandatory = Column(Boolean, default=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<DocumentType(name='{self.name}')>"


class SchoolMaster(Base):
    """
    School Master - maintains a list of schools for 10th/12th dropdowns.
    Schools can be uploaded via PDF/CSV/Excel in bulk.
    
    Structure based on Tamil Nadu school block information:
    - district: District name
    - block: Block/Taluk name  
    - name: School name
    - school_address: Full address of the school
    - pincode: Postal code
    """
    __tablename__ = "school_master"

    name = Column(String(500), nullable=False, index=True)  # school_name from PDF
    block = Column(String(200), nullable=True, index=True)  # block_name from PDF
    district = Column(String(200), nullable=True, index=True)  # district from PDF
    school_address = Column(String(500), nullable=True)  # school_address from PDF
    pincode = Column(String(6), nullable=True, index=True)  # pincode from PDF
    state = Column(String(100), nullable=True, default="Tamil Nadu")
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<SchoolMaster(name='{self.name}', block='{self.block}', district='{self.district}')>"


class SchoolListUpload(Base):
    """
    Tracks school list file uploads for audit purposes.
    """
    __tablename__ = "school_list_uploads"

    file_name = Column(String(500), nullable=False)
    file_url = Column(String(1000), nullable=True)
    record_count = Column(Integer, default=0)
    upload_status = Column(String(50), default="completed")  # completed, failed, partial

    def __repr__(self):
        return f"<SchoolListUpload(file_name='{self.file_name}', records={self.record_count})>"
