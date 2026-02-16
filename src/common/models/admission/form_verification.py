import enum
from datetime import datetime
from components.db.base_model import Base
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UUID,
)
from sqlalchemy.orm import relationship


class VerificationStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    FORM_PRINTED = "FORM_PRINTED"
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    CERTIFICATES_RECEIVED = "CERTIFICATES_RECEIVED"
    VERIFIED = "VERIFIED"
    PROVISIONALLY_ALLOTTED = "PROVISIONALLY_ALLOTTED"
    REJECTED = "REJECTED"


class AdmissionFormVerification(Base):
    """
    Model to track admission form printing and certificate verification process.
    Staff prints the form and verifies certificates without collecting them.
    """

    __tablename__ = "admission_form_verifications"

    # Student Reference
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Status tracking
    status = Column(
        Enum(VerificationStatusEnum),
        default=VerificationStatusEnum.PENDING,
        nullable=False,
    )

    # Form printing
    form_printed = Column(Boolean, default=False, nullable=False)
    form_printed_at = Column(DateTime, nullable=True)
    form_printed_by = Column(UUID(as_uuid=True), nullable=True)  # Staff ID

    # Application Received (New workflow - Form Verification Team receives printed form)
    application_received = Column(Boolean, default=False, nullable=False)
    application_received_at = Column(DateTime, nullable=True)
    application_received_by = Column(UUID(as_uuid=True), nullable=True)  # Form Verification Team Staff ID

    # Certificate verification (key requirement)
    certificate_verified = Column(Boolean, default=False, nullable=False)
    certificate_verified_at = Column(DateTime, nullable=True)
    certificate_verified_by = Column(
        UUID(as_uuid=True), nullable=True
    )  # Staff ID who verified

    # Provisionally Allotted status
    provisionally_allotted = Column(Boolean, default=False, nullable=False)
    provisionally_allotted_at = Column(DateTime, nullable=True)
    provisionally_allotted_by = Column(UUID(as_uuid=True), nullable=True)  # Staff ID

    # Additional tracking
    verification_remarks = Column(Text, nullable=True)  # Comments from verifier
    documents_checked = Column(
        String, nullable=True
    )  # Comma-separated list of docs checked

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    student = relationship("AdmissionStudent", back_populates="form_verification")
    submitted_certificates = relationship(
        "SubmittedCertificate",
        back_populates="form_verification",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<AdmissionFormVerification(student_id={self.student_id}, status={self.status})>"


class SubmittedCertificate(Base):
    """
    Model to track submitted certificates for form verification
    Stores certificate uploads with metadata
    """

    __tablename__ = "submitted_certificates"

    # Reference to form verification record
    form_verification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_form_verifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to required certificate
    required_certificate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_required_certificates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Certificate file details
    file_path = Column(String(500), nullable=True)  # S3 or local path
    file_name = Column(String(200), nullable=True)
    file_size = Column(String(50), nullable=True)  # e.g., "2.5MB"
    file_type = Column(String(50), nullable=True)  # e.g., "pdf", "jpg"

    # Verification status
    is_received = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    received_at = Column(DateTime, nullable=True)
    received_by = Column(UUID(as_uuid=True), nullable=True)  # Staff ID who received
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=True), nullable=True)  # Staff ID who verified

    # Comments
    remarks = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    form_verification = relationship(
        "AdmissionFormVerification", back_populates="submitted_certificates"
    )
    required_certificate = relationship("AdmissionRequiredCertificates")

    def __repr__(self):
        return f"<SubmittedCertificate(form_verification_id={self.form_verification_id}, is_received={self.is_received})>"
