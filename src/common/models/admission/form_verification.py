import enum
from components.db.base_model import Base
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Integer,
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
    Track admission form printing and certificate verification process.
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
    form_printed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )

    # Application Received
    application_received = Column(Boolean, default=False, nullable=False)
    application_received_at = Column(DateTime, nullable=True)
    application_received_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )

    # Certificate verification
    certificate_verified = Column(Boolean, default=False, nullable=False)
    certificate_verified_at = Column(DateTime, nullable=True)
    certificate_verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )

    # Provisionally Allotted
    provisionally_allotted = Column(Boolean, default=False, nullable=False)
    provisionally_allotted_at = Column(DateTime, nullable=True)
    provisionally_allotted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )

    # Additional tracking
    verification_remarks = Column(Text, nullable=True)
    documents_checked = Column(
        String(2000), nullable=True
    )  # Comma-separated list of docs checked
    # created_at / updated_at inherited from Base

    # Relationships
    student = relationship("AdmissionStudent", back_populates="form_verification", lazy="selectin")
    submitted_certificates = relationship(
        "SubmittedCertificate",
        back_populates="form_verification",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<AdmissionFormVerification(student_id={self.student_id}, status={self.status})>"


class SubmittedCertificate(Base):
    """
    Track submitted certificates for form verification.
    """

    __tablename__ = "submitted_certificates"

    # Reference to form verification record
    form_verification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_form_verifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to document type (was required_certificate_id)
    document_type_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Certificate file details
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)  # bytes
    file_type = Column(String(50), nullable=True)

    # Verification status
    is_received = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    received_at = Column(DateTime, nullable=True)
    received_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )

    # Comments
    remarks = Column(Text, nullable=True)
    # created_at / updated_at inherited from Base

    # Relationships
    form_verification = relationship(
        "AdmissionFormVerification", back_populates="submitted_certificates", lazy="selectin"
    )
    required_certificate = relationship("DocumentType", lazy="selectin")

    def __repr__(self):
        return f"<SubmittedCertificate(form_verification_id={self.form_verification_id}, is_received={self.is_received})>"
