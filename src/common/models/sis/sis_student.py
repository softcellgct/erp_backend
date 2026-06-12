import enum

from components.db.base_model import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
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

    def __repr__(self):
        return f"<SISStudentProfile(admission_student_id={self.admission_student_id})>"
