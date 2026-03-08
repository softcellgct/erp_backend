from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from uuid import UUID

from common.models.master.annual_task import AcademicYear
from common.schemas.master.annual_task import (
    AcademicYearSchema,
    AcademicYearCourseCreate,
    UpdateAcademicYearSchema,
)

class AnnualTaskService: # Or AcademicService
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_academic_year(self, data: AcademicYearSchema):
        data_dict = data.model_dump()
        course_configs = data_dict.pop("course_configs", None)
        
        academic_year = AcademicYear(**data_dict)
        self.db.add(academic_year)
        await self.db.flush()  # Flush to get the ID

        # if the new year is meant to be active (status or admission_active)
        # make sure no other year for the same institution remains active.
        if academic_year.status or academic_year.admission_active:
            await self._deactivate_other_years(
                academic_year.institution_id, academic_year.id,
                deactivate_status=academic_year.status,
                deactivate_admission=academic_year.admission_active,
            )

        if course_configs:
            from common.models.master.annual_task import AcademicYearCourse
            for config in course_configs:
                # config is a dict because of model_dump
                course_fee = AcademicYearCourse(
                    academic_year_id=academic_year.id,
                    course_id=config["course_id"],
                    application_fee=config["application_fee"],
                    is_active=config["is_active"]
                )
                self.db.add(course_fee)
        
        await self.db.commit()
        await self.db.refresh(academic_year)
        return academic_year


    async def list_academic_years(self):
        result = await self.db.execute(select(AcademicYear))
        return result.scalars().all()

    async def get_academic_year(self, academic_year_id: UUID):
        result = await self.db.execute(select(AcademicYear).where(AcademicYear.id == academic_year_id))
        academic_year = result.scalar_one_or_none()
        if not academic_year:
            raise HTTPException(status_code=404, detail="Academic Year not found")
        return academic_year

    async def update_academic_year(self, academic_year_id: UUID, data: UpdateAcademicYearSchema):
        # using the update schema allows callers to send only the fields
        # they want to modify; `id` is ignored here because the target is
        # already specified separately.
        data_dict = data.model_dump(exclude_unset=True)
        data_dict.pop("id", None)
        course_configs = data_dict.pop("course_configs", None)

        # capture flags before the update for enforcing uniqueness later
        status_flag = data_dict.get("status")
        admission_flag = data_dict.get("admission_active")

        result = await self.db.execute(
            update(AcademicYear).where(AcademicYear.id == academic_year_id).values(**data_dict)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Academic Year not found")

        # if the caller tried to set either flag true, deactivate others
        if status_flag or admission_flag:
            # need institution id of this year -- load the record
            stmt = select(AcademicYear).where(AcademicYear.id == academic_year_id)
            res = await self.db.execute(stmt)
            ay = res.scalar_one_or_none()
            if ay:
                await self._deactivate_other_years(
                    ay.institution_id,
                    academic_year_id,
                    deactivate_status=status_flag,
                    deactivate_admission=admission_flag,
                )

        if course_configs is not None:
             from common.models.master.annual_task import AcademicYearCourse
             # For each config, check if it exists for this year and course
             for config in course_configs:
                 # Check if exists
                 stmt = select(AcademicYearCourse).where(
                     AcademicYearCourse.academic_year_id == academic_year_id,
                     AcademicYearCourse.course_id == config["course_id"]
                 )
                 res = await self.db.execute(stmt)
                 existing_course = res.scalar_one_or_none()

                 if existing_course:
                     existing_course.application_fee = config["application_fee"]
                     existing_course.is_active = config["is_active"]
                 else:
                     new_course = AcademicYearCourse(
                         academic_year_id=academic_year_id,
                         course_id=config["course_id"],
                         application_fee=config["application_fee"],
                         is_active=config["is_active"]
                     )
                     self.db.add(new_course)

        await self.db.commit()
        return await self.get_academic_year(academic_year_id)
    
    async def delete_academic_year(self, academic_year_id: UUID):
        result = await self.db.execute(
            update(AcademicYear).where(AcademicYear.id == academic_year_id).values(status=False)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Academic Year not found")
        await self.db.commit()
        return {"message": "Academic Year deactivated"}


    async def set_active_academic_year(self, academic_year_id: UUID):
        """
        Activate the given academic year and deactivate other academic years
        for the same institution. This ensures only one active academic year
        per institution.  Admission flag of others is cleared as well.
        """
        # Fetch the academic year
        stmt = select(AcademicYear).where(AcademicYear.id == academic_year_id)
        res = await self.db.execute(stmt)
        ay = res.scalar_one_or_none()
        if not ay:
            raise HTTPException(status_code=404, detail="Academic Year not found")

        # Deactivate other academic years for the same institution
        await self._deactivate_other_years(ay.institution_id, academic_year_id,
                                          deactivate_status=True,
                                          deactivate_admission=True)

        # Activate this one
        ay.status = True
        await self.db.commit()
        await self.db.refresh(ay)
        return ay


    async def _deactivate_other_years(self, institution_id: UUID, keep_id: UUID | None = None, deactivate_status: bool | None = True, deactivate_admission: bool | None = True):
        """Helper to mark other academic years for an institution inactive.

        Parameters
        ----------
        institution_id: UUID
            institution whose years should be filtered
        keep_id: UUID | None
            id of year that should be left untouched (typically the one being
            created/updated).  If None all years for the institution are affected.
        deactivate_status: bool | None
            if True, set `status` to False on matched rows.  If None do not
            touch the column.  (Passing False has no effect but is accepted for
            symmetry with `deactivate_admission`).
        deactivate_admission: bool | None
            similar to deactivate_status but for `admission_active`.
        """
        values = {}
        if deactivate_status:
            values["status"] = False
        if deactivate_admission:
            values["admission_active"] = False
        if not values:
            return
        stmt = update(AcademicYear).where(
            AcademicYear.institution_id == institution_id
        )
        if keep_id:
            stmt = stmt.where(AcademicYear.id != keep_id)
        await self.db.execute(stmt.values(**values))

    async def set_admission_active(self, academic_year_id: UUID):
        """Mark a single academic year as having admissions open.

        Other years for the same institution will have
        `admission_active` cleared.  This does not touch the `status` field,
        although in practice an open-admission year is usually active as well.
        """
        stmt = select(AcademicYear).where(AcademicYear.id == academic_year_id)
        res = await self.db.execute(stmt)
        ay = res.scalar_one_or_none()
        if not ay:
            raise HTTPException(status_code=404, detail="Academic Year not found")

        await self._deactivate_other_years(ay.institution_id, academic_year_id,
                                          deactivate_status=False,
                                          deactivate_admission=True)
        ay.admission_active = True
        await self.db.commit()
        await self.db.refresh(ay)
        return ay

    async def assign_course_to_academic_year(self, academic_year_id: UUID, data: AcademicYearCourseCreate):
        # Verify academic year exists
        await self.get_academic_year(academic_year_id)
        
        # Verify course exists
        from common.models.master.institution import Course
        course_res = await self.db.execute(select(Course).where(Course.id == data.course_id))
        if not course_res.scalar_one_or_none():
             raise HTTPException(status_code=404, detail="Course not found")

        from common.models.master.annual_task import AcademicYearCourse
        
        # Check if assignment already exists
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == academic_year_id,
            AcademicYearCourse.course_id == data.course_id
        )
        result = await self.db.execute(stmt)
        existing_assignment = result.scalar_one_or_none()

        if existing_assignment:
            # Update existing assignment
            existing_assignment.application_fee = data.application_fee
            existing_assignment.is_active = data.is_active
            await self.db.commit()
            return existing_assignment
        else:
            # Create new assignment
            new_assignment = AcademicYearCourse(
                academic_year_id=academic_year_id,
                course_id=data.course_id,
                application_fee=data.application_fee,
                is_active=data.is_active
            )
            self.db.add(new_assignment)
            await self.db.commit()
            await self.db.refresh(new_assignment)
            return new_assignment

    async def get_courses_for_academic_year(self, academic_year_id: UUID):
        from common.models.master.annual_task import AcademicYearCourse
        # Verify academic year exists
        await self.get_academic_year(academic_year_id)
        
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == academic_year_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_course_config(self, academic_year_id: UUID, course_id: UUID, data: AcademicYearCourseCreate):
         from common.models.master.annual_task import AcademicYearCourse
         
         stmt = select(AcademicYearCourse).where(
             AcademicYearCourse.academic_year_id == academic_year_id,
             AcademicYearCourse.course_id == course_id
         )
         result = await self.db.execute(stmt)
         assignment = result.scalar_one_or_none()
         
         if not assignment:
             raise HTTPException(status_code=404, detail="Course assignment not found for this academic year")
             
         assignment.application_fee = data.application_fee
         assignment.is_active = data.is_active
         await self.db.commit()
         await self.db.refresh(assignment)
         return assignment

    async def remove_course_from_academic_year(self, academic_year_id: UUID, course_id: UUID):
        from common.models.master.annual_task import AcademicYearCourse
        
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == academic_year_id,
            AcademicYearCourse.course_id == course_id
        )
        result = await self.db.execute(stmt)
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Course assignment not found for this academic year")
            
        await self.db.delete(assignment)
        await self.db.commit()
        return {"message": "Course assignment removed successfully"}
