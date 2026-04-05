from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship



from sqlalchemy import JSON, Integer, Date, Enum as SAEnum
import enum


class GenderEnum(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    TRANSGENDER = "Transgender"
    ALL = "All"

class FineCalculationEnum(str, enum.Enum):
    NOT_APPLICABLE = "Fine not applicable"
    FIXED_AMOUNT = "Fixed amount"
    PERCENTAGE = "Percentage"
    PER_DAY = "Per day"

class PayerTypeEnum(str, enum.Enum):
    STUDENT = "STUDENT"
    GOVERNMENT = "GOVERNMENT"
    SCHOLARSHIP = "SCHOLARSHIP"

class FeeStructure(Base):
    __tablename__ = "fee_structures"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year_id: Mapped[UUID] = mapped_column(ForeignKey("financial_years.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # New Fields based on UI
    semester_period_id: Mapped[UUID | None] = mapped_column(ForeignKey("semester_periods.id", ondelete="SET NULL"), nullable=True, index=True)  # Fee Period
    admission_type_id: Mapped[UUID | None] = mapped_column(ForeignKey("admission_types.id", ondelete="SET NULL"), nullable=True, index=True)
    quota_id: Mapped[UUID | None] = mapped_column(ForeignKey("seat_quotas.id", ondelete="SET NULL"), nullable=True, index=True)
    gender: Mapped[GenderEnum] = mapped_column(SAEnum(GenderEnum, name="gender_enum_v2", values_callable=lambda obj: [e.value for e in obj]), default=GenderEnum.ALL, nullable=False)
    
    degree_id: Mapped[UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    
    course_duration_years: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    semesters_per_year: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    fg_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sc_st_scholarship: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fg_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sc_st_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fg_amount_by_semester: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"1": 5000, "2": 5000, ...}
    batch: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships — only items eager-loaded; lookups are lazy to avoid N+1 explosion
    items = relationship("FeeStructureItem", back_populates="fee_structure", cascade="all, delete-orphan", lazy="selectin")
    financial_year = relationship("FinancialYear", back_populates="fee_structures", lazy="selectin")
    admission_year = relationship("AcademicYear", lazy="selectin")
    
    semester_period = relationship("SemesterPeriod", lazy="selectin")
    admission_type = relationship("AdmissionType", lazy="selectin")
    quota = relationship("SeatQuota", lazy="selectin")
    degree = relationship("Course", lazy="selectin")
    department = relationship("Department", lazy="selectin")


class FeeStructureItem(Base):
    __tablename__ = "fee_structure_items"

    fee_structure_id: Mapped[UUID] = mapped_column(ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    # New fields for item details
    last_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    fine_calculation: Mapped[FineCalculationEnum] = mapped_column(SAEnum(FineCalculationEnum, name="fine_calculation_enum_v2", values_callable=lambda obj: [e.value for e in obj]), default=FineCalculationEnum.NOT_APPLICABLE, nullable=False)
    fine_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    fine_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    
    amount_by_year: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    amount_by_semester: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"1": 25000, "2": 25000, ...}
    payer_type: Mapped[PayerTypeEnum] = mapped_column(
        SAEnum(PayerTypeEnum, name="payer_type_enum", values_callable=lambda obj: [e.value for e in obj]),
        default=PayerTypeEnum.STUDENT,
        nullable=False,
    )
    order: Mapped[int] = mapped_column(nullable=True)

    # Relationships — lazy="selectin" to avoid circular eager load with FeeStructure
    fee_structure = relationship("FeeStructure", back_populates="items", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")
    fee_sub_head = relationship("FeeSubHead", back_populates="structure_items", lazy="selectin")

