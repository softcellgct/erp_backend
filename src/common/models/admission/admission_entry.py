import enum
from components.db.base_model import Base
from common.models.master.admission_masters import AdmissionType, SeatQuota
from sqlalchemy import (
    Column,
    String,
    Date,
    Enum,
    Float,
    Boolean,
    Integer,
    Numeric,
    Text,
    ForeignKey,
    DateTime,
    func,
    UUID,
    JSON,
    select
)
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
    ENQUIRY = "ENQUIRY"
    ENQUIRED = "ENQUIRED"
    BOOKED = "BOOKED"
    APPLIED = "APPLIED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    DOCUMENTS_VERIFIED = "DOCUMENTS_VERIFIED"
    FEE_PENDING = "FEE_PENDING"
    FEE_RECEIVED = "FEE_RECEIVED"
    ADMISSION_GRANTED = "ADMISSION_GRANTED"
    FORM_VERIFICATION_PENDING = "FORM_VERIFICATION_PENDING"
    FORM_VERIFIED = "FORM_VERIFIED"
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    PROVISIONALLY_ALLOTTED = "PROVISIONALLY_ALLOTTED"
    ENROLLED = "ENROLLED"
    WAITLISTED = "WAITLISTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    ON_HOLD = "ON_HOLD"


class AdmissionTypeEnum(str, enum.Enum):
    GENERAL = "General"
    LATERAL = "Lateral"
    TRANSFER = "Transfer"
    DIRECT = "Direct"
    MANAGEMENT = "Management"
    COUNSELING = "Counseling"


class SourceEnum(str, enum.Enum):
    GATE_ENQUIRY = "GATE_ENQUIRY"
    DIRECT_ENTRY = "DIRECT_ENTRY"
    COUNSELING = "COUNSELING"


class VisitStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"


class AdmissionStudent(Base):
    __tablename__ = "admission_students"

    # Enquiry Number
    enquiry_number = Column(String(50), unique=True, index=True, nullable=False)
    application_number = Column(String(50), unique=True, index=True, nullable=True)

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
    parent_income = Column(Numeric(12, 2), nullable=True)

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
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True, index=True)
    year = Column(String(20), nullable=True)  # Year of study
    branch = Column(String(200), nullable=True)

    # Relationships linked to Foreign Keys
    institution = relationship("Institution")
    department = relationship("Department")
    course = relationship("Course")

    # Previous Academic Level
    previous_academic_level = Column(Enum(PreviousAcademicLevelEnum), nullable=True)

    # Lateral Entry
    is_lateral_entry = Column(Boolean, default=False, nullable=False)

    # Vehicle Details
    has_vehicle = Column(Boolean, default=False)
    vehicle_number = Column(String(20), nullable=True)

    # Gate Visit Tracking (merged from admission_visitors)
    source = Column(
        Enum(SourceEnum), default=SourceEnum.DIRECT_ENTRY, nullable=False
    )
    image_url = Column(String(500), nullable=True)
    native_place = Column(String(255), nullable=True)
    visit_status = Column(
        Enum(VisitStatusEnum), nullable=True
    )
    check_in_time = Column(DateTime(timezone=True), nullable=True)
    check_out_time = Column(DateTime(timezone=True), nullable=True)
    check_out_remarks = Column(String(255), nullable=True)

    # Category and Quota
    # Category and Quota
    admission_quota_id = Column(UUID(as_uuid=True), ForeignKey("seat_quotas.id"), nullable=True, index=True)
    category = Column(Enum(CategoryEnum), nullable=True)
    quota_type = Column(
        String(50), nullable=True
    )  # Sports, Cultural, NCC, Ex-Serviceman
    special_quota = Column(String(100), nullable=True)  # 7.5%, First Graduate, etc.
    scholarships = Column(String(200), nullable=True)
    boarding_place = Column(String(200), nullable=True)
    admission_type_id = Column(UUID(as_uuid=True), ForeignKey("admission_types.id"), nullable=True, index=True)
    
    academic_year_id = Column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True
    )
    
    # Documents Checklist
    documents_submitted = Column(JSON, nullable=True)  # List of document IDs or names

    status = Column(
        Enum(AdmissionStatusEnum), default=AdmissionStatusEnum.ENQUIRED, nullable=False
    )

    # Post-admission details
    roll_number = Column(String(50), nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    current_semester = Column(Integer, nullable=True)
    is_sem1_active = Column(Boolean, default=False, nullable=False)
    enrolled_at = Column(DateTime, nullable=True)
    fee_structure_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_structures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_fee_structure_locked = Column(Boolean, default=False, nullable=False)
    fee_structure_locked_at = Column(DateTime, nullable=True)
    fee_structure_locked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )

    # Relationships linked to Foreign Keys
    admission_quota = relationship("SeatQuota")
    admission_type = relationship("AdmissionType")
    fee_structure = relationship("FeeStructure", lazy="select")

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
    form_verification = relationship(
        "AdmissionFormVerification",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    department_change_requests = relationship(
        "DepartmentChangeRequest",
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Reference relationships (from gate enquiry)
    consultancy_reference = relationship(
        "ConsultancyReference", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    staff_reference = relationship(
        "StaffReference", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    student_reference = relationship(
        "StudentReference", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    other_reference = relationship(
        "OtherReference", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self):
        return f"<AdmissionStudent(id={self.id}, name='{self.name}', gate_pass='{self.gate_pass_number}')>"

    @classmethod
    async def create(cls, request, session, data_list):
        """Override create to automatically generate application numbers"""
        from components.generator.utils.get_user_from_request import get_user_id
        from sqlalchemy.inspection import inspect

        if not data_list:
            raise ValueError("No data provided to create records.")

        objects = []
        errors = []
        skipped = 0
        
        for idx, data in enumerate(data_list):
            user_id = await get_user_id(request)
            obj_data = data.dict() if hasattr(data, "dict") else data
            obj_data["created_by"] = user_id
            
            # Check for duplicate Aadhaar number
            if obj_data.get("aadhaar_number"):
                existing = await session.execute(
                    select(cls.id).where(cls.aadhaar_number == obj_data["aadhaar_number"])
                )
                if existing.scalar_one_or_none():
                    errors.append({
                        "row": idx + 1,
                        "error": f"Duplicate Aadhaar number: {obj_data['aadhaar_number']} already exists"
                    })
                    skipped += 1
                    continue
            
            # Generate enquiry number if not provided
            if not obj_data.get("enquiry_number"):
                from apps.admission.services import generate_enquiry_number
                obj_data["enquiry_number"] = await generate_enquiry_number(session, obj_data.get("institution_id"))
            
            # Resolve admission_quota_id if it's a string
            if isinstance(obj_data.get("admission_quota_id"), str):
                from common.models.master.admission_masters import SeatQuota
                quota_result = await session.execute(
                    select(SeatQuota.id).where(SeatQuota.name == obj_data["admission_quota_id"])
                )
                obj_data["admission_quota_id"] = quota_result.scalar_one_or_none()

            # Resolve admission_type_id if it's a string
            if isinstance(obj_data.get("admission_type_id"), str):
                from common.models.master.admission_masters import AdmissionType
                type_result = await session.execute(
                    select(AdmissionType.id).where(AdmissionType.name == obj_data["admission_type_id"])
                )
                obj_data["admission_type_id"] = type_result.scalar_one_or_none()
            
            # Handle nested relationships - convert dicts/lists to model instances
            mapper = inspect(cls)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in obj_data and obj_data[rel_name] is not None:
                    rel_data = obj_data[rel_name]
                    related_model = rel.mapper.class_
                    # If a single related object is provided as a dict -> create instance
                    if not rel.uselist and isinstance(rel_data, dict):
                        # Extract only scalar fields, not relationships
                        rel_mapper = inspect(related_model)
                        scalar_data = {k: v for k, v in rel_data.items() if k not in rel_mapper.relationships}
                        obj_data[rel_name] = related_model(**scalar_data)
                    # If a list of related objects is provided -> convert each
                    elif rel.uselist and isinstance(rel_data, list):
                        new_list = []
                        rel_mapper = inspect(related_model)
                        for item in rel_data:
                            if isinstance(item, dict):
                                # Extract only scalar fields, not relationships
                                scalar_data = {k: v for k, v in item.items() if k not in rel_mapper.relationships}
                                new_list.append(related_model(**scalar_data))
                            elif hasattr(item, '_sa_instance_state'):
                                new_list.append(item)
                            else:
                                raise ValueError(f"Invalid related item for relationship '{rel_name}': {item}")
                        obj_data[rel_name] = new_list
            
            objects.append(cls(**obj_data))

        if objects:
            session.add_all(objects)
            await session.commit()

        return {
            "created": len(objects),
            "skipped": skipped,
            "errors": errors
        }

    @classmethod
    async def update(cls, request, session, data_list):
        """
        Prevent department/course edits when the student's fee structure is locked.
        """
        if not data_list:
            raise ValueError("No data provided for update.")

        normalized_items = []
        student_ids = []
        for data_obj in data_list:
            data = (
                data_obj.dict(exclude_unset=True)
                if hasattr(data_obj, "dict")
                else data_obj
            )
            student_id = data.get("id")
            if not student_id:
                raise ValueError("Each object must have an 'id' field.")
            normalized_items.append(data)
            student_ids.append(student_id)

        result = await session.execute(
            select(cls).where(cls.id.in_(student_ids), cls.deleted_at.is_(None))
        )
        existing_students = {student.id: student for student in result.scalars().all()}

        def as_str(value):
            return str(value) if value is not None else None

        for data in normalized_items:
            student = existing_students.get(data["id"])
            if not student or not getattr(student, "is_fee_structure_locked", False):
                continue

            has_dept_change = (
                "department_id" in data
                and as_str(data.get("department_id")) != as_str(student.department_id)
            )
            has_course_change = (
                "course_id" in data
                and as_str(data.get("course_id")) != as_str(student.course_id)
            )

            if has_dept_change or has_course_change:
                raise ValueError(
                    "Fee structure is locked for this student; department/course change is not allowed."
                )

        return await super().update(request, session, data_list)


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
    school_block = Column(String(200), nullable=True)
    board = Column(String(100), nullable=True)  # State Board, CBSE, ICSE, etc.
    year_of_passing = Column(String(4), nullable=True)
    marks = Column(Float, nullable=True)
    total_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)
    # created_at / updated_at inherited from Base

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
    school_block = Column(String(200), nullable=True)
    board = Column(String(100), nullable=True)  # State Board, CBSE, ICSE, etc.
    year_of_passing = Column(String(4), nullable=True)
    total_marks = Column(Float, nullable=True)
    obtained_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)

    # Subject-wise marks (legacy aggregate columns kept for backward compatibility)
    maths_mark = Column(Float, nullable=True)
    physics_mark = Column(Float, nullable=True)
    chemistry_mark = Column(Float, nullable=True)
    pcm_percentage = Column(Float, nullable=True)
    cutoff_mark = Column(Float, nullable=True)

    # School details
    school_address = Column(Text, nullable=True)
    medium_of_study = Column(String(50), nullable=True)

    # Relationship
    student = relationship("AdmissionStudent", back_populates="hsc_details")
    subject_marks = relationship(
        "HSCSubjectMark",
        back_populates="hsc_details",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

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

    # Relationship
    student = relationship("AdmissionStudent", back_populates="diploma_details")

    def __repr__(self):
        return f"<DiplomaDetails(student_id={self.student_id}, college_name='{self.college_name}')>"


class HSCSubjectMark(Base):
    """
    Individual subject marks for HSC (12th) - supports all board types
    """

    __tablename__ = "hsc_subject_marks"

    hsc_details_id = Column(
        ForeignKey("hsc_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject_name = Column(String(100), nullable=False)  # e.g., Physics, Chemistry, Maths
    subject_variant = Column(String(100), nullable=True)  # e.g., Vocational, Practical
    total_marks = Column(Float, nullable=False)
    obtained_marks = Column(Float, nullable=False)

    # Relationship
    hsc_details = relationship("HSCDetails", back_populates="subject_marks")

    def __repr__(self):
        return f"<HSCSubjectMark(subject='{self.subject_name}', obtained={self.obtained_marks}/{self.total_marks})>"


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

    # Relationship
    student = relationship("AdmissionStudent", back_populates="pg_details")

    def __repr__(self):
        return f"<PGDetails(student_id={self.student_id}, degree_name='{self.degree_name}')>"
