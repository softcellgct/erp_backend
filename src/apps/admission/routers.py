from common.models.admission.consultancy import Consultancy
from common.schemas.admission.consultancy import (
    ConsultancyCreate,
    ConsultancyResponse,
    ConsultancyUpdate,
)
from components.db.db import get_db_session
from fastapi import APIRouter, Depends, HTTPException, status

from components.generator.routes import create_crud_routes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from common.schemas.admission.admission_entry import (
    AdmissionStudentCreate,
    AdmissionStudentResponse,
    AdmissionStudentUpdate,
    AdmissionStudentGrantAdmission,
)
from common.models.gate.visitor_model import AdmissionVisitor
from apps.admission.services import generate_enquiry_number
from sqlalchemy import select
from uuid import UUID

consultancy_router = APIRouter()

consultancy_crud_router = create_crud_routes(
    Consultancy,
    ConsultancyCreate,
    ConsultancyUpdate,
    ConsultancyResponse,
)

consultancy_router.include_router(
    consultancy_crud_router, prefix="/consultancies", tags=["Admission - Consultancies"]
)


admission_entry_router = APIRouter()

admission_entry_crud_router = create_crud_routes(
    AdmissionStudent,
    AdmissionStudentCreate,
    AdmissionStudentUpdate,
    AdmissionStudentResponse,
    AdmissionStudentResponse
)

admission_entry_router.include_router(
    admission_entry_crud_router, prefix="/admission-students", tags=["Admission - Admission Students"]
)

# Custom POST endpoint for granting admission
@admission_entry_router.post(
    "/admission-students",
    response_model=AdmissionStudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admission - Admission Students"],
    name="Create Admission Student",
    description="Create an admission student record and update the visitor status to ADMISSION_GRANTED"
)
async def create_admission_student(
    payload: AdmissionStudentGrantAdmission,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create admission student record with automatic application number generation.
    
    If visitor_id is provided in the payload:
    1. Generates a unique application number
    2. Updates the admission_visitors record status to ADMISSION_GRANTED
    3. Creates a new admission_students record with the provided payload and application number
    
    If visitor_id is not provided:
    1. Creates admission_students record without updating visitor status
    
    Args:
        payload: Admission student details (may include visitor_id)
        
    Returns:
        Created admission student record with generated application number
    """
    try:
        # Extract visitor_id from payload if present
        visitor_id = payload.visitor_id
        
        # Handle visitor status update if visitor_id is provided
        if visitor_id:
            # Fetch the admission visitor
            visitor_result = await db.execute(
                select(AdmissionVisitor).where(AdmissionVisitor.id == visitor_id)
            )
            admission_visitor = visitor_result.scalar_one_or_none()
            
            if not admission_visitor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Admission visitor with ID {visitor_id} not found"
                )
            
            # Generate unique enquiry number
            enquiry_number = await generate_enquiry_number(db, admission_visitor.institution_id)
            
            # Update admission visitor status to ADMISSION_GRANTED
            admission_visitor.status = AdmissionStatusEnum.ADMISSION_GRANTED
            db.add(admission_visitor)
        else:
            # Generate enquiry number even without visitor_id
            enquiry_number = await generate_enquiry_number(db)
        
        # Create new admission student record with enquiry number
        student_data = payload.dict()
        
        # Remove non-model fields
        student_data.pop('visitor_id', None)  # Remove visitor_id from payload
        
        # Add enquiry number
        student_data['enquiry_number'] = enquiry_number
        
        # Handle nested relationships - convert dicts to model instances
        mapper = inspect(AdmissionStudent)
        for rel_name, rel in mapper.relationships.items():
            if rel_name in student_data and student_data[rel_name] is not None:
                rel_data = student_data[rel_name]
                related_model = rel.mapper.class_
                # If a single related object is provided as a dict -> create instance
                if not rel.uselist and isinstance(rel_data, dict):
                    student_data[rel_name] = related_model(**rel_data)
                # If a list of related objects is provided -> convert each
                elif rel.uselist and isinstance(rel_data, list):
                    new_list = []
                    for item in rel_data:
                        if isinstance(item, dict):
                            new_list.append(related_model(**item))
                        else:
                            new_list.append(item)
                    student_data[rel_name] = new_list
        
        # Create admission student
        admission_student = AdmissionStudent(**student_data)
        
        db.add(admission_student)
        await db.commit()
        await db.refresh(admission_student)
        
        return admission_student
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create admission student: {str(e)}"
        )



admission_router = APIRouter()

@admission_router.get("/applied", tags=["Admission - Admission Students"])
async def get_applied_admission_students(
    db: AsyncSession = Depends(get_db_session)
):
    """Get all admission students with status 'APPLIED'."""
    result = await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.status == "APPLIED")
    )
    return result.scalars().all()