import enum
from components.db.base_model import Base
from sqlalchemy import (
    Column,
    String,
    Date,
    Enum,
    Float,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
)
from datetime import datetime
from sqlalchemy.orm import relationship


class GenderEnum(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"


class AdmissionQuotaEnum(str, enum.Enum):
    MANAGEMENT = "Management"
    GOVERNMENT = "Government"


class PreviousAcademicLevelEnum(str, enum.Enum):
    TENTH = "10th"
    TWELFTH = "12th"
    DIPLOMA = "Diploma"
    DEGREE = "Degree"


class CategoryEnum(str, enum.Enum):
    GENERAL = "General"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    MBC = "MBC"
    DNC = "DNC"
    OTHERS = "Others"


class AdmissionStatusEnum(str, enum.Enum):
    APPLIED = "Applied"
    DOCUMENTS_PENDING = "Documents Pending"
    DOCUMENTS_VERIFIED = "Documents Verified"
    FEE_PENDING = "Fee Pending"
    FEE_RECEIVED = "Fee Received"
    ADMISSION_GRANTED = "Admission Granted"
    ENROLLED = "Enrolled"
    WAITLISTED = "Waitlisted"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"
    ON_HOLD = "On Hold"


class AdmissionStudent(Base):
    __tablename__ = "admission_students"

    # Gate Pass and Reference
    gate_pass_number = Column(String(50), unique=True, index=True, nullable=True)
    reference_type = Column(String(100), nullable=True)

    # Personal Details
    name = Column(String(200), nullable=False, index=True)
    father_name = Column(String(200), nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    student_mobile = Column(String(15), nullable=True)
    parent_mobile = Column(String(15), nullable=True)
    aadhaar_number = Column(String(12), nullable=True, unique=True)

    # Religious and Social Details
    religion = Column(String(50), nullable=True)
    community = Column(String(50), nullable=True)
    caste = Column(String(50), nullable=True)
    parent_income = Column(Float, nullable=True)

    # Address Details
    door_no = Column(String(50), nullable=True)
    street_name = Column(String(200), nullable=True)
    village_name = Column(String(100), nullable=True)
    taluk = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    parent_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)

    # Degree & Branch Details
    campus = Column(String(200), nullable=True)  # Institution name
    department = Column(String(200), nullable=True)
    course = Column(String(200), nullable=True)  # Degree
    year = Column(String(20), nullable=True)  # Year of study
    branch = Column(String(200), nullable=True)

    # Previous Academic Level
    previous_academic_level = Column(Enum(PreviousAcademicLevelEnum), nullable=True)

    # Vehicle Details
    has_vehicle = Column(Boolean, default=False)
    vehicle_number = Column(String(20), nullable=True)

    # Category and Quota
    admission_quota = Column(Enum(AdmissionQuotaEnum), nullable=True)
    category = Column(Enum(CategoryEnum), nullable=True)
    quota_type = Column(
        String(50), nullable=True
    )  # Sports, Cultural, NCC, Ex-Serviceman
    special_quota = Column(String(100), nullable=True)  # 7.5%, First Graduate, etc.
    scholarships = Column(String(200), nullable=True)
    boarding_place = Column(String(200), nullable=True)
    status = Column(
        Enum(AdmissionStatusEnum), default=AdmissionStatusEnum.APPLIED, nullable=False
    )

    # Relationships
    sslc_details = relationship(
        "SSLCDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    hsc_details = relationship(
        "HSCDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    diploma_details = relationship(
        "DiplomaDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pg_details = relationship(
        "PGDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<AdmissionStudent(id={self.id}, name='{self.name}', gate_pass='{self.gate_pass_number}')>"


class SSLCDetails(Base):
    """
    10th (SSLC) Academic Details
    """

    __tablename__ = "sslc_details"

    student_id = Column(
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    register_number = Column(String(50), nullable=True)
    school_name = Column(String(200), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    marks = Column(Float, nullable=True)
    total_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    student = relationship("AdmissionStudent", back_populates="sslc_details")

    def __repr__(self):
        return f"<SSLCDetails(student_id={self.student_id}, register_number='{self.register_number}')>"


class HSCDetails(Base):
    """
    12th (HSC) Academic Details
    """

    __tablename__ = "hsc_details"

    student_id = Column(
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    register_number = Column(String(50), nullable=True)
    school_name = Column(String(200), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    total_marks = Column(Float, nullable=True)
    obtained_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)

    # Subject-wise marks
    maths_mark = Column(Float, nullable=True)
    physics_mark = Column(Float, nullable=True)
    chemistry_mark = Column(Float, nullable=True)
    pcm_percentage = Column(Float, nullable=True)
    cutoff_mark = Column(Float, nullable=True)

    # School details
    school_address = Column(Text, nullable=True)
    medium_of_study = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    student = relationship("AdmissionStudent", back_populates="hsc_details")

    def __repr__(self):
        return f"<HSCDetails(student_id={self.student_id}, register_number='{self.register_number}')>"


class DiplomaDetails(Base):
    """
    Diploma Academic Details
    """

    __tablename__ = "diploma_details"

    student_id = Column(
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    college_name = Column(String(200), nullable=True)
    department = Column(String(200), nullable=True)
    register_number = Column(String(50), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    percentage = Column(Float, nullable=True)
    cgpa = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    student = relationship("AdmissionStudent", back_populates="diploma_details")

    def __repr__(self):
        return f"<DiplomaDetails(student_id={self.student_id}, college_name='{self.college_name}')>"


class PGDetails(Base):
    """
    Degree / PG Academic Details
    """

    __tablename__ = "pg_details"

    student_id = Column(
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    degree_name = Column(String(100), nullable=True)
    department = Column(String(200), nullable=True)
    college_name = Column(String(200), nullable=True)
    register_number = Column(String(50), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    percentage = Column(Float, nullable=True)
    cgpa = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    student = relationship("AdmissionStudent", back_populates="pg_details")

    def __repr__(self):
        return f"<PGDetails(student_id={self.student_id}, degree_name='{self.degree_name}')>"
