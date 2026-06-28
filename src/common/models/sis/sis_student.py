import enum

from components.db.base_model import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
    func,
)
from sqlalchemy.orm import relationship


class HostelStatusEnum(str, enum.Enum):
    DAY_SCHOLAR = "Day Scholar"
    HOSTELLER = "Hosteller"
    DAY_BOARDER = "Day Boarder"


class BloodGroupEnum(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class EntryModeEnum(str, enum.Enum):
    """How a student entered the programme."""
    NORMAL = "NORMAL"
    LATERAL_ENTRY = "LATERAL_ENTRY"
    TRANSFER = "TRANSFER"


class AcademicStatusEnum(str, enum.Enum):
    """Current academic standing of a student in the SIS lifecycle."""
    ACTIVE = "ACTIVE"
    PROMOTED = "PROMOTED"
    GRADUATED = "GRADUATED"
    DISCONTINUED = "DISCONTINUED"
    TRANSFERRED = "TRANSFERRED"
    ALUMNI = "ALUMNI"


class SISStudentProfile(Base):
    """
    Additional SIS-specific student data not captured during admission.
    One-to-one with AdmissionStudent.
    """
    __tablename__ = "sis_student_profiles"

    admission_student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Extended personal details
    blood_group = Column(Enum(BloodGroupEnum), nullable=True)
    nationality = Column(String(100), nullable=True, default="Indian")
    mother_tongue = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    whatsapp_number = Column(String(15), nullable=True)

    # Special status
    differently_abled = Column(Boolean, default=False, nullable=False)
    differently_abled_type = Column(String(200), nullable=True)
    ex_serviceman_child = Column(Boolean, default=False, nullable=False)
    first_generation_graduate = Column(Boolean, default=False, nullable=False)

    # Family details
    mother_name = Column(String(200), nullable=True)
    mother_occupation = Column(String(200), nullable=True)
    father_occupation = Column(String(200), nullable=True)
    guardian_name = Column(String(200), nullable=True)
    guardian_relation = Column(String(100), nullable=True)
    guardian_mobile = Column(String(15), nullable=True)

    # Institutional
    register_number = Column(String(100), nullable=True, index=True)
    hostel_status = Column(Enum(HostelStatusEnum), nullable=True)
    photo_url = Column(String(500), nullable=True)

    # Bank account details
    bank_name = Column(String(200), nullable=True)
    bank_account_number = Column(String(50), nullable=True)
    bank_ifsc_code = Column(String(20), nullable=True)
    bank_branch_name = Column(String(200), nullable=True)
    bank_account_holder_name = Column(String(200), nullable=True)

    # Transfer Certificate details
    tc_number = Column(String(50), nullable=True)
    tc_date = Column(DateTime(timezone=True), nullable=True)
    tc_from_school = Column(String(200), nullable=True)
    tc_issued_by = Column(String(200), nullable=True)

    # Emergency contact
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_relation = Column(String(100), nullable=True)
    emergency_contact_mobile = Column(String(15), nullable=True)

    # Counselling details
    counselling_date = Column(DateTime(timezone=True), nullable=True)
    counselling_number = Column(String(50), nullable=True)
    allotment_order_number = Column(String(50), nullable=True)
    counselling_type = Column(String(50), nullable=True)

    # Government / institutional IDs
    emis_number = Column(String(50), nullable=True)
    umis_number = Column(String(50), nullable=True)
    abc_id = Column(String(50), nullable=True)

    # Quota / social status extras
    minority_status = Column(String(100), nullable=True)

    # Contact extras
    alternate_mobile = Column(String(15), nullable=True)

    # Extended communication address
    comm_address_line2 = Column(String(500), nullable=True)
    comm_country = Column(String(100), nullable=True, default="India")

    # Structured permanent address (separate from the single-text field in personal_details)
    perm_address_line1 = Column(String(500), nullable=True)
    perm_address_line2 = Column(String(500), nullable=True)
    perm_area_street = Column(String(500), nullable=True)
    perm_city = Column(String(100), nullable=True)
    perm_district = Column(String(100), nullable=True)
    perm_state = Column(String(100), nullable=True)
    perm_country = Column(String(100), nullable=True, default="India")
    perm_pincode = Column(String(10), nullable=True)

    # ── Academic progression — CURRENT position only.  Full history lives in
    # SISStudentAcademicHistory (sis_student_academic_history); never overwrite
    # year/semester without first appending a history record. ──
    current_year_of_study = Column(Integer, nullable=True)
    current_semester = Column(Integer, nullable=True)
    current_academic_year_id = Column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id"),
        nullable=True,
        index=True,
    )
    entry_mode = Column(Enum(EntryModeEnum, name="entry_mode_enum"), nullable=True)
    admission_batch = Column(String(20), nullable=True, index=True)
    graduation_year = Column(Integer, nullable=True)
    academic_status = Column(
        Enum(AcademicStatusEnum, name="academic_status_enum"),
        nullable=False,
        default=AcademicStatusEnum.ACTIVE,
        server_default=AcademicStatusEnum.ACTIVE.value,
    )

    # ── Promotion-eligibility holds (independent of the ON_HOLD admission status) ──
    academic_hold = Column(Boolean, default=False, nullable=False)
    disciplinary_hold = Column(Boolean, default=False, nullable=False)
    hold_reason = Column(String(500), nullable=True)

    # ── Lateral entry / diploma background (populated for LATERAL_ENTRY students) ──
    diploma_institution = Column(String(255), nullable=True)
    diploma_board = Column(String(255), nullable=True)
    diploma_register_number = Column(String(100), nullable=True)
    diploma_completion_year = Column(Integer, nullable=True)
    diploma_percentage = Column(String(20), nullable=True)
    diploma_cgpa = Column(String(20), nullable=True)
    diploma_branch = Column(String(255), nullable=True)
    diploma_certificate_number = Column(String(100), nullable=True)

    # Profile completion
    profile_completed_at = Column(DateTime(timezone=True), nullable=True)
    profile_completed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
    )

    student = relationship(
        "AdmissionStudent",
        lazy="selectin",
        foreign_keys=[admission_student_id],
    )
    current_academic_year = relationship(
        "AcademicYear",
        lazy="selectin",
        foreign_keys=[current_academic_year_id],
    )

    def __repr__(self):
        return f"<SISStudentProfile(admission_student_id={self.admission_student_id})>"
