from sqlalchemy import select, update, or_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from common.models.master.institution import Institution, Department, Course, Class
from common.models.master.annual_task import AcademicYear, AcademicYearCourse
from fastapi import HTTPException
from uuid import UUID

class InstitutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Institution CRUD
    async def list_institutions(self):
        result = await self.db.execute(select(Institution))
        return result.scalars().all()

    async def get_institution(self, institution_id: UUID):
        result = await self.db.execute(select(Institution).where(Institution.id == institution_id))
        institution = result.scalar_one_or_none()
        if not institution:
            raise HTTPException(status_code=404, detail="Institution not found")
        return institution

    # Department CRUD
    async def create_department(self, data):
        # Validate institution exists
        await self.get_institution(data.institution_id)
        department = Department(**data.dict())
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def list_departments(self, academic_year_id: str | None = None):
        """
        List departments. For now, returns all active departments regardless of academic_year_id.
        The academic_year_id parameter is accepted for future filtering support.
        """
        # Return all active departments
        result = await self.db.execute(select(Department).where(Department.is_active == True))
        return result.scalars().all()

    async def get_department(self, department_id: UUID):
        result = await self.db.execute(select(Department).where(Department.id == department_id))
        department = result.scalar_one_or_none()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        return department

    async def update_department(self, department_id: UUID, data):
        if data.institution_id:
            await self.get_institution(data.institution_id)
        result = await self.db.execute(
            update(Department).where(Department.id == department_id).values(**data.dict(exclude_unset=True))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Department not found")
        await self.db.commit()
        return await self.get_department(department_id)

    # Course CRUD
    async def create_course(self, data):
        # Validate department exists
        await self.get_department(data.department_id)
        course = Course(**data.dict())
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def list_courses(self):
        result = await self.db.execute(select(Course))
        return result.scalars().all()

    async def get_course(self, course_id: UUID):
        result = await self.db.execute(select(Course).where(Course.id == course_id))
        course = result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course

    async def update_course(self, course_id: UUID, data):
        if data.department_id:
            await self.get_department(data.department_id)
        result = await self.db.execute(
            update(Course).where(Course.id == course_id).values(**data.dict(exclude_unset=True))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Course not found")
        await self.db.commit()
        return await self.get_course(course_id)

    async def delete_course(self, course_id: UUID):
        result = await self.db.execute(
            update(Course).where(Course.id == course_id).values(is_active=False)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Course not found")
        await self.db.commit()
        return {"message": "Course deactivated"}

    # Class CRUD
    async def create_class(self, data):
        # Validate course exists
        await self.get_course(data.course_id)
        class_obj = Class(**data.dict())
        self.db.add(class_obj)
        await self.db.commit()
        await self.db.refresh(class_obj)
        return class_obj

    async def list_classes(self):
        result = await self.db.execute(select(Class))
        return result.scalars().all()

    async def get_class(self, class_id: UUID):
        result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_obj = result.scalar_one_or_none()
        if not class_obj:
            raise HTTPException(status_code=404, detail="Class not found")
        return class_obj

    async def update_class(self, class_id: UUID, data):
        if data.course_id:
            await self.get_course(data.course_id)
        result = await self.db.execute(
            update(Class).where(Class.id == class_id).values(**data.dict(exclude_unset=True))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Class not found")
        await self.db.commit()
        return await self.get_class(class_id)

    async def delete_class(self, class_id: UUID):
        result = await self.db.execute(
            update(Class).where(Class.id == class_id).values(is_active=False)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Class not found")
        await self.db.commit()
        return {"message": "Class deactivated"}

    # Hostel CRUD
    async def list_hostels(self, institution_id: UUID | None = None):
        from common.models.master.institution import Hostel
        stmt = select(Hostel)
        if institution_id:
            stmt = stmt.where(Hostel.institution_id == institution_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ========== NEW: Cascading filter methods for admission form ==========

    async def list_admission_active_years(self, institution_id: UUID | None = None):
        """
        Get academic years where admission_active=True.
        Status (academic active/inactive) does not affect admission availability.
        Optionally filtered by institution_id.
        """
        stmt = select(AcademicYear).where(
            AcademicYear.admission_active == True,
            AcademicYear.deleted_at.is_(None),
        ).options(
            selectinload(AcademicYear.institution).selectinload(Institution.departments),
            selectinload(AcademicYear.available_courses)
        )
        if institution_id:
            stmt = stmt.where(AcademicYear.institution_id == institution_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_departments_by_institution(self, institution_id: UUID):
        """
        Get active departments for a specific institution.
        """
        stmt = select(Department).where(
            Department.institution_id == institution_id,
            Department.is_active == True,
            Department.deleted_at.is_(None),
        ).order_by(Department.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_courses_by_department(self, department_id: UUID):
        """
        Get active courses for a specific department.
        """
        stmt = select(Course).where(
            Course.department_id == department_id,
            Course.is_active == True,
            Course.deleted_at.is_(None),
        ).order_by(Course.title)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_active_courses_for_year(self, academic_year_id: UUID):
        """
        Get courses linked to an academic year via AcademicYearCourse where is_active=True.
        Returns the Course objects.
        """
        from sqlalchemy.orm import selectinload
        stmt = (
            select(AcademicYearCourse)
            .options(selectinload(AcademicYearCourse.course))
            .where(
                AcademicYearCourse.academic_year_id == academic_year_id,
                AcademicYearCourse.is_active == True,
                AcademicYearCourse.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        year_courses = result.scalars().all()
        return [yc.course for yc in year_courses if yc.course and yc.course.is_active]

    async def list_admission_eligible_programs(self, institution_id: UUID, academic_year_id: UUID):
        """
        Return departments and courses eligible for admission entry selection.

        Eligibility rule:
        - Department is active
        - Course is active
        - AcademicYearCourse config exists for selected year
        - AcademicYearCourse config is active
        - AcademicYearCourse.application_fee > 0
        """
        stmt = (
            select(Department, Course)
            .join(Course, Course.department_id == Department.id)
            .join(AcademicYearCourse, AcademicYearCourse.course_id == Course.id)
            .where(
                Department.institution_id == institution_id,
                or_(Department.is_active == True, Department.is_active.is_(None)),
                Department.deleted_at.is_(None),
                or_(Course.is_active == True, Course.is_active.is_(None)),
                Course.deleted_at.is_(None),
                AcademicYearCourse.academic_year_id == academic_year_id,
                or_(AcademicYearCourse.is_active == True, AcademicYearCourse.is_active.is_(None)),
                func.coalesce(AcademicYearCourse.application_fee, 0) > 0,
                AcademicYearCourse.deleted_at.is_(None),
            )
            .order_by(Department.name, Course.title)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        dept_map: dict[str, dict] = {}
        courses: list[dict] = []

        for dept, course in rows:
            dept_key = str(dept.id)
            if dept_key not in dept_map:
                dept_map[dept_key] = {
                    "id": dept.id,
                    "name": dept.name,
                    "code": getattr(dept, "code", None),
                }

            courses.append(
                {
                    "id": course.id,
                    "title": course.title,
                    "short_name": getattr(course, "short_name", None),
                    "level": getattr(course, "level", None),
                    "department_id": course.department_id,
                }
            )

        return {
            "departments": list(dept_map.values()),
            "courses": courses,
        }
