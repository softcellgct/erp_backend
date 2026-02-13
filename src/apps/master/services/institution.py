from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from common.models.master.institution import Institution, Department, Course, Class
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
