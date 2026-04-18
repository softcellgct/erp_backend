import enum
from typing import Any

from components.db.base_model import Base
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UUID,
    func,
    select,
    update,
)
from sqlalchemy.inspection import inspect
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


class AdmissionGateEntry(Base):
    __tablename__ = "admission_gate_entries"

    gate_pass_number = Column(String(50), unique=True, index=True, nullable=False)
    reference_type = Column(String(100), nullable=True)

    student_name = Column(String(200), nullable=False, index=True)
    parent_or_guardian_name = Column(String(200), nullable=True)
    mobile_number = Column(String(15), nullable=True)
    aadhar_number = Column(String(12), nullable=True, index=True)

    native_place = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=True)

    vehicle = Column(Boolean, default=False, nullable=False)
    vehicle_number = Column(String(20), nullable=True)

    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)

    visit_status = Column(Enum(VisitStatusEnum), nullable=False, default=VisitStatusEnum.CHECKED_IN)
    check_in_time = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    check_out_time = Column(DateTime(timezone=True), nullable=True)
    check_out_remarks = Column(String(255), nullable=True)

    status = Column(Enum(AdmissionStatusEnum), default=AdmissionStatusEnum.ENQUIRY, nullable=False)
    enquiry_number = Column(String(50), unique=True, index=True, nullable=True)

    institution = relationship("Institution", lazy="selectin")

    admission_student = relationship(
        "AdmissionStudent",
        back_populates="gate_entry",
        uselist=False,
        lazy="selectin",
    )

    consultancy_reference = relationship(
        "ConsultancyReference",
        back_populates="gate_entry",
        uselist=False,
        lazy="selectin",
    )
    staff_reference = relationship(
        "StaffReference",
        back_populates="gate_entry",
        uselist=False,
        lazy="selectin",
    )
    student_reference = relationship(
        "StudentReference",
        back_populates="gate_entry",
        uselist=False,
        lazy="selectin",
    )
    other_reference = relationship(
        "OtherReference",
        back_populates="gate_entry",
        uselist=False,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<AdmissionGateEntry(id={self.id}, pass='{self.gate_pass_number}', name='{self.student_name}')>"


class AdmissionStudent(Base):
    __tablename__ = "admission_students"

    # Enquiry / application
    enquiry_number = Column(String(50), unique=True, index=True, nullable=False)
    application_number = Column(String(50), unique=True, index=True, nullable=True)
    
    # Student name (denormalized from personal_details for direct access)
    name = Column(String(200), nullable=False, index=True)

    # Link to new gate table (primary source for gate entry data)
    gate_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_gate_entries.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    documents_submitted = Column(JSON, nullable=True)

    status = Column(Enum(AdmissionStatusEnum), default=AdmissionStatusEnum.ENQUIRED, nullable=False)
    source = Column(Enum(SourceEnum), default=SourceEnum.GATE_ENQUIRY, nullable=False)

    # Post-admission
    roll_number = Column(String(50), nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    current_semester = Column(Integer, nullable=True)
    is_lateral_entry = Column(Boolean, default=False, nullable=False)
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

    # Foreign key relationships
    fee_structure = relationship("FeeStructure", lazy="selectin")

    gate_entry = relationship("AdmissionGateEntry", back_populates="admission_student", lazy="selectin")

    # New normalized detail tables
    personal_details = relationship(
        "AdmissionStudentPersonalDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    program_details = relationship(
        "AdmissionStudentProgramDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    previous_academic_details = relationship(
        "AdmissionStudentPreviousAcademicDetails",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    form_verification = relationship(
        "AdmissionFormVerification",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    department_change_requests = relationship(
        "DepartmentChangeRequest",
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # References retained for admission-level reporting
    consultancy_reference = relationship(
        "ConsultancyReference",
        back_populates="student",
        foreign_keys="ConsultancyReference.student_id",
        uselist=False,
        lazy="selectin",
    )
    staff_reference = relationship(
        "StaffReference",
        back_populates="student",
        foreign_keys="StaffReference.student_id",
        uselist=False,
        lazy="selectin",
    )
    student_reference = relationship(
        "StudentReference",
        back_populates="student",
        foreign_keys="StudentReference.student_id",
        uselist=False,
        lazy="selectin",
    )
    other_reference = relationship(
        "OtherReference",
        back_populates="student",
        foreign_keys="OtherReference.student_id",
        uselist=False,
        lazy="selectin",
    )

    deposits = relationship(
        "StudentDeposit",
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<AdmissionStudent(id={self.id}, enquiry='{self.enquiry_number}')>"

    @classmethod
    async def _link_gate_references_to_student(
        cls,
        session,
        gate_entry_id,
        student_id,
    ):
        from common.models.gate.visitor_model import (
            ConsultancyReference,
            OtherReference,
            StaffReference,
            StudentReference,
        )

        reference_models = [
            ConsultancyReference,
            StaffReference,
            StudentReference,
            OtherReference,
        ]

        for model in reference_models:
            await session.execute(
                update(model)
                .where(model.gate_entry_id == gate_entry_id, model.student_id.is_(None))
                .values(student_id=student_id)
            )

    @staticmethod
    def _sync_program_fields(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Keep legacy top-level fields and normalized program_details fields in sync.

        This avoids sparse/null drift when clients send either shape.
        """
        program_keys = [
            "academic_year_id",
            "admission_quota_id",
            "category",
            "quota_type",
            "special_quota",
            "scholarships",
            "boarding_place",
            "admission_type_id",
        ]

        raw_program = payload.get("program_details")
        if isinstance(raw_program, dict):
            program_details = dict(raw_program)
        elif hasattr(raw_program, "dict"):
            program_details = raw_program.dict(exclude_unset=True)
        else:
            program_details = {}

        for key in program_keys:
            top_val = payload.get(key)
            nested_val = program_details.get(key)

            if top_val is not None and nested_val is None:
                program_details[key] = top_val
            elif top_val is None and nested_val is not None:
                payload[key] = nested_val

        if program_details:
            payload["program_details"] = program_details

        return payload

    @classmethod
    async def create(cls, request, session, data_list):
        """Create admission students and synchronize split-detail tables."""
        from components.generator.utils.get_user_from_request import get_user_id

        if not data_list:
            raise ValueError("No data provided to create records.")

        objects: list[AdmissionStudent] = []
        errors = []
        skipped = 0

        mapper = inspect(cls)
        relationship_map = mapper.relationships

        for idx, data in enumerate(data_list):
            user_id = await get_user_id(request)
            obj_data = data.dict() if hasattr(data, "dict") else dict(data)
            obj_data["created_by"] = user_id
            obj_data = cls._sync_program_fields(obj_data)

            visitor_id = obj_data.pop("visitor_id", None)
            gate_entry = None
            gate_entry_id = obj_data.get("gate_entry_id") or visitor_id
            if gate_entry_id:
                gate_entry = await session.get(AdmissionGateEntry, gate_entry_id)
                if gate_entry:
                    obj_data["gate_entry_id"] = gate_entry.id
                    if gate_entry.status == AdmissionStatusEnum.ENQUIRY:
                        gate_entry.status = AdmissionStatusEnum.ENQUIRED

            personal_details = obj_data.get("personal_details")
            name = None
            if isinstance(personal_details, dict):
                name = personal_details.get("name")
            elif hasattr(personal_details, "name"):
                name = personal_details.name

            if not name:
                errors.append({"row": idx + 1, "error": "Student name is required in personal details"})
                skipped += 1
                continue

            # Populate name on main student object (denormalized)
            obj_data["name"] = name

            aadhaar = None
            if isinstance(personal_details, dict):
                aadhaar = personal_details.get("aadhaar_number")
            elif hasattr(personal_details, "aadhaar_number"):
                aadhaar = personal_details.aadhaar_number

            if aadhaar:
                from sqlalchemy import join
                existing = await session.execute(
                    select(cls.id).join(AdmissionStudentPersonalDetails).where(
                        AdmissionStudentPersonalDetails.aadhaar_number == aadhaar,
                        cls.deleted_at.is_(None),
                    )
                )
                if existing.scalar_one_or_none():
                    errors.append(
                        {
                            "row": idx + 1,
                            "error": f"Duplicate Aadhaar number: {aadhaar} already exists",
                        }
                    )
                    skipped += 1
                    continue

            if not obj_data.get("enquiry_number"):
                from apps.admission.services import generate_enquiry_number
                
                program_details = obj_data.get("program_details")
                inst_id = None
                if isinstance(program_details, dict):
                    inst_id = program_details.get("institution_id")
                elif hasattr(program_details, "institution_id"):
                    inst_id = program_details.institution_id

                obj_data["enquiry_number"] = await generate_enquiry_number(
                    session,
                    inst_id,
                )

            if isinstance(obj_data.get("admission_quota_id"), str):
                from common.models.master.admission_masters import SeatQuota

                quota_result = await session.execute(
                    select(SeatQuota.id).where(SeatQuota.name == obj_data["admission_quota_id"])
                )
                obj_data["admission_quota_id"] = quota_result.scalar_one_or_none()

            if isinstance(obj_data.get("admission_type_id"), str):
                from common.models.master.admission_masters import AdmissionType

                type_result = await session.execute(
                    select(AdmissionType.id).where(AdmissionType.name == obj_data["admission_type_id"])
                )
                obj_data["admission_type_id"] = type_result.scalar_one_or_none()

            # Convert relationship dict/list payloads into model instances.
            for rel_name, rel in relationship_map.items():
                if rel_name not in obj_data or obj_data[rel_name] is None:
                    continue

                rel_data = obj_data[rel_name]
                related_model = rel.mapper.class_

                if not rel.uselist and isinstance(rel_data, dict):
                    rel_mapper = inspect(related_model)
                    scalar_data = {
                        key: value
                        for key, value in rel_data.items()
                        if key in rel_mapper.columns
                    }
                    obj_data[rel_name] = related_model(**scalar_data)
                elif rel.uselist and isinstance(rel_data, list):
                    rel_mapper = inspect(related_model)
                    new_list = []
                    for item in rel_data:
                        if isinstance(item, dict):
                            scalar_data = {
                                key: value
                                for key, value in item.items()
                                if key in rel_mapper.columns
                            }
                            new_list.append(related_model(**scalar_data))
                        elif hasattr(item, "_sa_instance_state"):
                            new_list.append(item)
                        else:
                            raise ValueError(
                                f"Invalid related item for relationship '{rel_name}': {item}"
                            )
                    obj_data[rel_name] = new_list

            valid_keys = set(mapper.columns.keys()) | set(mapper.relationships.keys())
            filtered_data = {key: value for key, value in obj_data.items() if key in valid_keys}

            objects.append(cls(**filtered_data))

        if objects:
            session.add_all(objects)
            await session.flush()

            for student in objects:
                if student.gate_entry_id:
                    await cls._link_gate_references_to_student(
                        session,
                        gate_entry_id=student.gate_entry_id,
                        student_id=student.id,
                    )

            await session.commit()

        return {
            "created": len(objects),
            "ids": [str(obj.id) for obj in objects],
            "skipped": skipped,
            "errors": errors,
        }

    @classmethod
    async def update(cls, request, session, data_list):
        """Update admission students and synchronize split-detail tables."""
        if not data_list:
            raise ValueError("No data provided for update.")

        normalized_items = []
        student_ids = []

        for data_obj in data_list:
            data = data_obj.dict(exclude_unset=True) if hasattr(data_obj, "dict") else dict(data_obj)
            data = cls._sync_program_fields(data)
            student_id = data.get("id")
            if not student_id:
                raise ValueError("Each object must have an 'id' field.")

            visitor_id = data.pop("visitor_id", None)
            gate_entry = None
            gate_entry_id = data.get("gate_entry_id") or visitor_id
            if gate_entry_id:
                gate_entry = await session.get(AdmissionGateEntry, gate_entry_id)
                if gate_entry:
                    data["gate_entry_id"] = gate_entry.id
                    if gate_entry.status == AdmissionStatusEnum.ENQUIRY:
                        gate_entry.status = AdmissionStatusEnum.ENQUIRED

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
            
            # Sync name from personal_details if provided
            personal_details = data.get("personal_details")
            if personal_details:
                name = None
                if isinstance(personal_details, dict):
                    name = personal_details.get("name")
                elif hasattr(personal_details, "name"):
                    name = personal_details.name
                if name:
                    data["name"] = name
            
            if not student or not getattr(student, "is_fee_structure_locked", False):
                continue

            program_details = data.get("program_details")
            dept_id = None
            course_id = None
            if isinstance(program_details, dict):
                dept_id = program_details.get("department_id")
                course_id = program_details.get("course_id")
            elif hasattr(program_details, "department_id"):
                dept_id = program_details.department_id
                course_id = program_details.course_id

            # We need to find the student's existing program_details department
            existing_dept_id = None
            existing_course_id = None
            if student.program_details:
                existing_dept_id = student.program_details.department_id
                existing_course_id = student.program_details.course_id

            has_dept_change = (
                dept_id is not None
                and as_str(dept_id) != as_str(existing_dept_id)
            )
            has_course_change = (
                course_id is not None
                and as_str(course_id) != as_str(existing_course_id)
            )

            if has_dept_change or has_course_change:
                raise ValueError(
                    "Fee structure is locked for this student; department/course change is not allowed."
                )

        updated_count = await super().update(request, session, normalized_items)

        for data in normalized_items:
            gate_entry_id = data.get("gate_entry_id")
            if gate_entry_id:
                await cls._link_gate_references_to_student(
                    session,
                    gate_entry_id=gate_entry_id,
                    student_id=data["id"],
                )

        await session.commit()
        return updated_count


class AdmissionStudentPersonalDetails(Base):
    __tablename__ = "admission_student_personal_details"

    admission_student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    name = Column(String(200), nullable=False)
    father_name = Column(String(200), nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    student_mobile = Column(String(15), nullable=True)
    parent_mobile = Column(String(15), nullable=True)
    aadhaar_number = Column(String(12), nullable=True, index=True)

    religion = Column(String(50), nullable=True)
    community = Column(String(50), nullable=True)
    caste = Column(String(50), nullable=True)
    parent_income = Column(Numeric(12, 2), nullable=True)

    door_no = Column(String(50), nullable=True)
    street_name = Column(String(200), nullable=True)
    village_name = Column(String(100), nullable=True)
    taluk = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    parent_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)

    student = relationship("AdmissionStudent", back_populates="personal_details", lazy="selectin")


class AdmissionStudentProgramDetails(Base):
    __tablename__ = "admission_student_program_details"

    admission_student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    campus = Column(String(200), nullable=True)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True, index=True)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True)

    year = Column(String(20), nullable=True)
    branch = Column(String(200), nullable=True)
    previous_academic_level = Column(Enum(PreviousAcademicLevelEnum), nullable=True)
    is_lateral_entry = Column(Boolean, default=False, nullable=False)

    admission_quota_id = Column(UUID(as_uuid=True), ForeignKey("seat_quotas.id"), nullable=True, index=True)
    category = Column(Enum(CategoryEnum), nullable=True)
    quota_type = Column(String(50), nullable=True)
    special_quota = Column(String(100), nullable=True)
    scholarships = Column(String(200), nullable=True)
    boarding_place = Column(String(200), nullable=True)
    admission_type_id = Column(UUID(as_uuid=True), ForeignKey("admission_types.id"), nullable=True, index=True)

    student = relationship("AdmissionStudent", back_populates="program_details", lazy="selectin")
    institution = relationship("Institution", lazy="selectin")
    department = relationship("Department", lazy="selectin")
    course = relationship("Course", lazy="selectin")
    admission_quota = relationship("SeatQuota", lazy="selectin")
    admission_type = relationship("AdmissionType", lazy="selectin")


class AdmissionStudentPreviousAcademicDetails(Base):
    __tablename__ = "admission_student_previous_academic_details"

    admission_student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    sslc = Column(JSON, nullable=True)
    hsc = Column(JSON, nullable=True)
    diploma = Column(JSON, nullable=True)
    degree = Column(JSON, nullable=True)

    student = relationship("AdmissionStudent", back_populates="previous_academic_details", lazy="selectin")


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
    school_district = Column(String(200), nullable=True)
    board = Column(String(100), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    marks = Column(Float, nullable=True)
    total_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)

    student = relationship("AdmissionStudent", lazy="selectin")

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
    school_district = Column(String(200), nullable=True)
    board = Column(String(100), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    total_marks = Column(Float, nullable=True)
    obtained_marks = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)

    maths_mark = Column(Float, nullable=True)
    physics_mark = Column(Float, nullable=True)
    chemistry_mark = Column(Float, nullable=True)
    pcm_percentage = Column(Float, nullable=True)
    cutoff_mark = Column(Float, nullable=True)

    school_address = Column(Text, nullable=True)
    medium_of_study = Column(String(50), nullable=True)

    student = relationship("AdmissionStudent", lazy="selectin")
    subject_marks = relationship(
        "HSCSubjectMark",
        back_populates="hsc_details",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
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

    student = relationship("AdmissionStudent", lazy="selectin")

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

    subject_name = Column(String(100), nullable=False)
    subject_variant = Column(String(100), nullable=True)
    total_marks = Column(Float, nullable=False)
    obtained_marks = Column(Float, nullable=False)

    hsc_details = relationship("HSCDetails", back_populates="subject_marks", lazy="selectin")

    def __repr__(self):
        return (
            f"<HSCSubjectMark(subject='{self.subject_name}', "
            f"obtained={self.obtained_marks}/{self.total_marks})>"
        )


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

    student = relationship("AdmissionStudent", lazy="selectin")

    def __repr__(self):
        return f"<PGDetails(student_id={self.student_id}, degree_name='{self.degree_name}')>"
