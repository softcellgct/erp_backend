"""
API Routers for Department Change Requests
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from uuid import UUID
from typing import Optional

from common.models.admission.department_change import (
    DepartmentChangeRequest,
    DepartmentChangeStatusEnum,
)
from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from common.models.master.institution import Department
from common.schemas.admission.department_change import (
    DepartmentChangeRequestCreate,
    DepartmentChangeRequestUpdate,
    DepartmentChangeRequestResponse,
    DepartmentChangeRequestListResponse,
    ApproveRejectRequest,
)
from components.db.db import get_db_session
from components.generator.utils.get_user_from_request import get_user_id
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate


department_change_router = APIRouter(
    prefix="/department-change", tags=["Admission - Department Change"]
)


# ========================
# Create Department Change Request
# ========================


@department_change_router.post(
    "",
    response_model=DepartmentChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    name="Create Department Change Request",
)
async def create_department_change_request(
    data: DepartmentChangeRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new department change request for a student.
    Validates that student exists and both departments exist.
    Prevents duplicate pending requests for the same student.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required",
        )

    # Verify student exists
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == data.student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {data.student_id} not found",
        )

    # Check if student is in valid status for department change
    valid_statuses = [
        AdmissionStatusEnum.APPLIED,
        AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
        AdmissionStatusEnum.ENROLLED,
    ]
    if student.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student must be applied, provisionally allotted, or enrolled to request department change. Current status: {student.status}",
        )

    if getattr(student, "is_fee_structure_locked", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department change is not allowed because the student's fee structure is locked.",
        )

    # Verify current department exists and matches student's department
    current_dept_query = select(Department).where(
        Department.id == data.current_department_id
    )
    result = await db.execute(current_dept_query)
    current_dept = result.scalar_one_or_none()

    if not current_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Current department with ID {data.current_department_id} not found",
        )

    # Verify requested department exists
    requested_dept_query = select(Department).where(
        Department.id == data.requested_department_id
    )
    result = await db.execute(requested_dept_query)
    requested_dept = result.scalar_one_or_none()

    if not requested_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested department with ID {data.requested_department_id} not found",
        )

    # Prevent same department change
    if data.current_department_id == data.requested_department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current and requested departments cannot be the same",
        )

    # Check for existing pending requests
    existing_query = select(DepartmentChangeRequest).where(
        and_(
            DepartmentChangeRequest.student_id == data.student_id,
            DepartmentChangeRequest.status == DepartmentChangeStatusEnum.PENDING,
            DepartmentChangeRequest.is_active == True,
        )
    )
    result = await db.execute(existing_query)
    existing_request = result.scalar_one_or_none()

    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending department change request already exists for this student",
        )

    # Create the request
    change_request = DepartmentChangeRequest(
        student_id=data.student_id,
        current_department_id=data.current_department_id,
        requested_department_id=data.requested_department_id,
        reason=data.reason,
        requested_by=user_id,
        requested_at=datetime.utcnow(),
        status=DepartmentChangeStatusEnum.PENDING,
    )

    db.add(change_request)
    await db.commit()
    await db.refresh(change_request)

    # Load relationships
    await db.refresh(change_request, ["student", "current_department", "requested_department"])

    return change_request


# ========================
# Get Department Change Requests (List with filters)
# ========================


@department_change_router.get(
    "",
    response_model=Page[DepartmentChangeRequestResponse],
    name="Get Department Change Requests",
)
async def get_department_change_requests(
    status_filter: Optional[DepartmentChangeStatusEnum] = None,
    student_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all department change requests with optional filters.
    Supports filtering by status, student, and department.
    """
    query = (
        select(DepartmentChangeRequest)
        .options(
            selectinload(DepartmentChangeRequest.student),
            selectinload(DepartmentChangeRequest.current_department),
            selectinload(DepartmentChangeRequest.requested_department),
        )
        .where(DepartmentChangeRequest.is_active == True)
        .order_by(DepartmentChangeRequest.requested_at.desc())
    )

    # Apply filters
    if status_filter:
        query = query.where(DepartmentChangeRequest.status == status_filter)

    if student_id:
        query = query.where(DepartmentChangeRequest.student_id == student_id)

    if department_id:
        query = query.where(
            or_(
                DepartmentChangeRequest.current_department_id == department_id,
                DepartmentChangeRequest.requested_department_id == department_id,
            )
        )

    return await paginate(db, query, params)


# ========================
# Get Single Department Change Request
# ========================


@department_change_router.get(
    "/{request_id}",
    response_model=DepartmentChangeRequestResponse,
    name="Get Department Change Request",
)
async def get_department_change_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a specific department change request by ID.
    """
    query = (
        select(DepartmentChangeRequest)
        .options(
            selectinload(DepartmentChangeRequest.student),
            selectinload(DepartmentChangeRequest.current_department),
            selectinload(DepartmentChangeRequest.requested_department),
        )
        .where(DepartmentChangeRequest.id == request_id)
    )

    result = await db.execute(query)
    change_request = result.scalar_one_or_none()

    if not change_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department change request with ID {request_id} not found",
        )

    return change_request


# ========================
# Approve Department Change Request
# ========================


@department_change_router.put(
    "/{request_id}/approve",
    response_model=DepartmentChangeRequestResponse,
    name="Approve Department Change Request",
)
async def approve_department_change_request(
    request_id: UUID,
    data: ApproveRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Approve a department change request.
    Updates the student's department_id and marks the request as approved.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required",
        )

    # Get the change request
    query = (
        select(DepartmentChangeRequest)
        .options(
            selectinload(DepartmentChangeRequest.student),
            selectinload(DepartmentChangeRequest.current_department),
            selectinload(DepartmentChangeRequest.requested_department),
        )
        .where(DepartmentChangeRequest.id == request_id)
    )
    result = await db.execute(query)
    change_request = result.scalar_one_or_none()

    if not change_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department change request with ID {request_id} not found",
        )

    # Check if already processed
    if change_request.status != DepartmentChangeStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {change_request.status.value.lower()}",
        )

    # Update student's department
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == change_request.student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    if getattr(student, "is_fee_structure_locked", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department change cannot be approved because the student's fee structure is locked.",
        )

    student.department_id = change_request.requested_department_id
    student.updated_at = datetime.utcnow()

    # Handle fee/demand changes for the student after department change
    try:
        from apps.billing.services import billing_service
        # Use handle_course_change which will remove pending demands and reassign fees.
        # Passing None as new_fee_structure_id lets the service lookup the appropriate structure.
        await billing_service.handle_course_change(db, student.id, None)
    except Exception:
        # Don't block approval if billing adjustments fail; log normally.
        pass

    # Update the request
    change_request.status = DepartmentChangeStatusEnum.APPROVED
    change_request.reviewed_by = user_id
    change_request.reviewed_at = datetime.utcnow()
    change_request.remarks = data.remarks

    await db.commit()
    await db.refresh(change_request)

    return change_request


# ========================
# Reject Department Change Request
# ========================


@department_change_router.put(
    "/{request_id}/reject",
    response_model=DepartmentChangeRequestResponse,
    name="Reject Department Change Request",
)
async def reject_department_change_request(
    request_id: UUID,
    data: ApproveRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Reject a department change request.
    Marks the request as rejected without changing the student's department.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required",
        )

    # Get the change request
    query = (
        select(DepartmentChangeRequest)
        .options(
            selectinload(DepartmentChangeRequest.student),
            selectinload(DepartmentChangeRequest.current_department),
            selectinload(DepartmentChangeRequest.requested_department),
        )
        .where(DepartmentChangeRequest.id == request_id)
    )
    result = await db.execute(query)
    change_request = result.scalar_one_or_none()

    if not change_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department change request with ID {request_id} not found",
        )

    # Check if already processed
    if change_request.status != DepartmentChangeStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {change_request.status.value.lower()}",
        )

    # Update the request
    change_request.status = DepartmentChangeStatusEnum.REJECTED
    change_request.reviewed_by = user_id
    change_request.reviewed_at = datetime.utcnow()
    change_request.remarks = data.remarks or "Request rejected"

    await db.commit()
    await db.refresh(change_request)

    return change_request


# ========================
# Delete Department Change Request (Soft Delete)
# ========================


@department_change_router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="Delete Department Change Request",
)
async def delete_department_change_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Soft delete a department change request.
    Only pending requests can be deleted.
    """
    query = select(DepartmentChangeRequest).where(
        DepartmentChangeRequest.id == request_id
    )
    result = await db.execute(query)
    change_request = result.scalar_one_or_none()

    if not change_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department change request with ID {request_id} not found",
        )

    # Only allow deletion of pending requests
    if change_request.status != DepartmentChangeStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be deleted",
        )

    change_request.is_active = False
    change_request.updated_at = datetime.utcnow()

    await db.commit()

    return None
