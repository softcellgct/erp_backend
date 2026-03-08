"""
API Routers for Admission Form Verification
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, File, UploadFile, Query
from sqlalchemy import select, and_, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload
from datetime import datetime
from uuid import UUID
from typing import List, Optional

from common.models.admission.form_verification import (
    AdmissionFormVerification,
    VerificationStatusEnum,
    SubmittedCertificate,
)
from common.models.admission.admission_entry import AdmissionStudent
from common.models.master.admission_masters import DocumentType
from common.schemas.admission.form_verification import (
    AdmissionFormVerificationResponse,
    AdmissionFormVerificationUpdate,
    PrintFormRequest,
    VerifyCertificateRequest,
    SubmittedCertificateResponse,
    SubmittedCertificateCreate,
    SubmittedCertificateUpdate,
)
from components.db.db import get_db_session
from components.generator.utils.get_user_from_request import get_user_id
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_pagination import Page, add_pagination
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
import logging

logger = logging.getLogger(__name__)


async def _safe_commit(db: AsyncSession, msg: str | None = None):
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"{msg or 'DB commit failed'}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


verification_router = APIRouter(
    prefix="/admission-form-verification", tags=["Admission - Form Verification"]
)


# ========================
# Print Form Endpoint
# ========================


@verification_router.post(
    "/{student_id}/print-form",
    response_model=AdmissionFormVerificationResponse,
    name="Print Admission Form",
)
async def print_admission_form(
    student_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Print admission form for a student.
    Creates or updates the verification record and marks form as printed.
    Uses upsert to handle race conditions safely.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Check if student exists
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {student_id} not found",
        )

    # Use upsert to safely handle concurrent requests
    stmt = pg_insert(AdmissionFormVerification).values(
        student_id=student_id,
        form_printed=True,
        form_printed_at=datetime.utcnow(),
        form_printed_by=user_id,
        status=VerificationStatusEnum.FORM_PRINTED,
    ).on_conflict_do_update(
        index_elements=['student_id'],
        set_={
            'form_printed': True,
            'form_printed_at': datetime.utcnow(),
            'form_printed_by': user_id,
            'status': VerificationStatusEnum.FORM_PRINTED,
            'updated_at': datetime.utcnow(),
        }
    ).returning(AdmissionFormVerification)

    result = await db.execute(stmt)
    verification = result.scalar_one()
    
    await _safe_commit(db)

    return verification


# ========================
# Verify Certificate Endpoint
# ========================


@verification_router.post(
    "/{student_id}/verify-certificate",
    response_model=AdmissionFormVerificationResponse,
    name="Verify Certificate",
)
async def verify_certificate(
    student_id: UUID,
    data: VerifyCertificateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Verify student certificate (certificate is NOT collected, only verified).
    Updates the verification status based on the verification result.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Check if student exists
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {student_id} not found",
        )

    # Get verification record
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found. Please print the form first.",
        )

    # Check if form was printed
    if not verification.form_printed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form must be printed before certificate verification.",
        )

    # Update verification details
    if data.certificate_verified:
        verification.certificate_verified = True
        verification.certificate_verified_at = datetime.utcnow()
        verification.certificate_verified_by = user_id
        verification.status = VerificationStatusEnum.VERIFIED
    else:
        # If certificate not verified, mark as rejected
        verification.status = VerificationStatusEnum.REJECTED

    if data.verification_remarks:
        verification.verification_remarks = data.verification_remarks

    if data.documents_checked:
        verification.documents_checked = data.documents_checked

    await _safe_commit(db)
    await db.refresh(verification)

    return verification


# ========================
# Get Verification Status Endpoint
# ========================


@verification_router.get(
    "/{student_id}",
    response_model=AdmissionFormVerificationResponse,
    name="Get Form Verification Status",
)
async def get_verification_status(
    student_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """
    Get the form verification status for a specific student.
    """
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found for this student.",
        )

    return verification


# ========================
# Get All Verifications (Paginated)
# ========================


@verification_router.get(
    "",
    response_model=Page[AdmissionFormVerificationResponse],
    name="Get All Form Verifications",
)
async def get_all_verifications(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all form verification records with pagination.
    """
    query = select(AdmissionFormVerification)
    return await paginate(db, query)


# ========================
# Get Verifications by Status
# ========================


@verification_router.get(
    "/status/{status}",
    response_model=Page[AdmissionFormVerificationResponse],
    name="Get Verifications by Status",
)
async def get_verifications_by_status(
    status: VerificationStatusEnum,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all form verification records filtered by status.
    Status can be: PENDING, FORM_PRINTED, VERIFIED, REJECTED
    """
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.status == status
    )
    return await paginate(db, query)


# ========================
# Create Initial Verification Record
# ========================


@verification_router.post(
    "/{student_id}/initialize",
    response_model=AdmissionFormVerificationResponse,
    name="Initialize Form Verification",
)
async def initialize_verification(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initialize a form verification record for a student after admission is granted.
    """
    # Check if student exists
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {student_id} not found",
        )

    # Check if verification record already exists
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form verification record already exists for this student.",
        )

    # Create new verification record
    verification = AdmissionFormVerification(
        student_id=student_id, status=VerificationStatusEnum.PENDING
    )
    db.add(verification)
    await _safe_commit(db)
    await db.refresh(verification)

    return verification


# ========================
# Update Verification Remarks
# ========================


@verification_router.patch(
    "/{student_id}/remarks",
    response_model=AdmissionFormVerificationResponse,
    name="Update Verification Remarks",
)
async def update_verification_remarks(
    student_id: UUID,
    data: AdmissionFormVerificationUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update verification remarks and documents checked information.
    """
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found.",
        )

    if data.verification_remarks is not None:
        verification.verification_remarks = data.verification_remarks

    if data.documents_checked is not None:
        verification.documents_checked = data.documents_checked

    await _safe_commit(db)
    await db.refresh(verification)

    return verification



# ========================
# Mark Application as Received (Form Verification Team)
# ========================


@verification_router.post(
    "/{student_id}/mark-application-received",
    response_model=AdmissionFormVerificationResponse,
    name="Mark Application as Received",
)
async def mark_application_received(
    student_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Mark application as received by the Form Verification Team.
    They use application number to mark when they receive the printed form.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Check if student exists
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {student_id} not found",
        )

    if not student.application_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student does not have an application number",
        )

    # Get verification record
    query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found.",
        )

    # Update status
    verification.application_received = True
    verification.application_received_at = datetime.utcnow()
    verification.application_received_by = user_id
    verification.status = VerificationStatusEnum.APPLICATION_RECEIVED

    await _safe_commit(db)
    await db.refresh(verification)

    return verification


# ========================
# Get Required Certificates for a Student
# ========================


@verification_router.get(
    "/{student_id}/required-certificates",
    response_model=List[dict],
    name="Get Required Certificates",
)
async def get_required_certificates(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get the list of required certificates for a student based on their
    academic year and department.
    """
    # Get student details
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {student_id} not found",
        )

    # Get all active required certificates (now from document_types directly)
    certs_query = select(DocumentType).where(
        DocumentType.is_active == True
    )
    result = await db.execute(certs_query)
    required_certs = result.scalars().all()

    # Get already submitted certificates
    submitted_query = select(SubmittedCertificate).where(
        SubmittedCertificate.form_verification_id
        == (
            select(AdmissionFormVerification.id).where(
                AdmissionFormVerification.student_id == student_id
            )
        )
    )
    result = await db.execute(submitted_query)
    submitted_certs = result.scalars().all()

    # Build response
    submitted_cert_map = {str(sc.document_type_id): sc for sc in submitted_certs}

    response = []
    for cert in required_certs:
        submitted = submitted_cert_map.get(str(cert.id))
        response.append(
            {
                "id": cert.id,
                "document_type_id": cert.id,
                "document_type_name": cert.name,
                "is_mandatory": cert.is_mandatory,
                "description": cert.description,
                "submitted_certificate_id": submitted.id if submitted else None,
                "is_received": submitted.is_received if submitted else False,
                "is_verified": submitted.is_verified if submitted else False,
                "file_name": submitted.file_name if submitted else None,
                "remarks": submitted.remarks if submitted else None,
            }
        )

    return response


# ========================
# Submit Certificate
# ========================


@verification_router.post(
    "/{student_id}/submit-certificate",
    response_model=SubmittedCertificateResponse,
    name="Submit Certificate",
)
async def submit_certificate(
    request: Request,
    student_id: UUID,
    document_type_id: UUID = Query(...),
    file: Optional[UploadFile] = File(None),
    remarks: Optional[str] = None,
    scope: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Submit a certificate for a student with file upload.
    The file is uploaded and stored in S3 or local storage.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Get or create form verification record
    fv_query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(fv_query)
    form_verification = result.scalar_one_or_none()

    if not form_verification:
        # Auto-create form verification record for the student
        form_verification = AdmissionFormVerification(student_id=student_id)
        db.add(form_verification)
        await _safe_commit(db)
        await db.refresh(form_verification)

    # Check if document type exists
    cert_query = select(DocumentType).where(
        DocumentType.id == document_type_id
    )
    result = await db.execute(cert_query)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document type not found",
        )

    # Check if already submitted
    existing_query = select(SubmittedCertificate).where(
        and_(
            SubmittedCertificate.form_verification_id == form_verification.id,
            SubmittedCertificate.document_type_id == document_type_id,
        )
    )
    result = await db.execute(existing_query)
    submitted_cert = result.scalar_one_or_none()

    # File handling
    file_path = None
    file_name = None
    file_size = None
    file_type = None

    if file:
        # TODO: Implement S3/Local file upload logic
        file_name = file.filename
        file_type = file.content_type
        # In real implementation, upload to S3 and get file_path
        file_path = f"certificates/{student_id}/{file.filename}"
        file_size = str(file.size) if hasattr(file, 'size') else "unknown"

    if submitted_cert:
        # Update existing record
        submitted_cert.is_received = True
        submitted_cert.received_at = datetime.utcnow()
        submitted_cert.received_by = user_id
        if file_path:
            submitted_cert.file_path = file_path
            submitted_cert.file_name = file_name
            submitted_cert.file_size = file_size
            submitted_cert.file_type = file_type
        if remarks:
            submitted_cert.remarks = remarks
    else:
        # Create new record
        submitted_cert = SubmittedCertificate(
            form_verification_id=form_verification.id,
            document_type_id=document_type_id,
            is_received=True,
            received_at=datetime.utcnow(),
            received_by=user_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            remarks=remarks,
        )
        db.add(submitted_cert)

    await _safe_commit(db)
    await db.refresh(submitted_cert)

    return submitted_cert


# ========================
# Get Submitted Certificates for Student
# ========================


@verification_router.get(
    "/{student_id}/submitted-certificates",
    response_model=List[SubmittedCertificateResponse],
    name="Get Submitted Certificates",
)
async def get_submitted_certificates(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all certificates submitted by a student
    """
    # Get or create form verification record
    fv_query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(fv_query)
    form_verification = result.scalar_one_or_none()

    if not form_verification:
        # Auto-create form verification record for the student
        form_verification = AdmissionFormVerification(student_id=student_id)
        db.add(form_verification)
        await _safe_commit(db)
        await db.refresh(form_verification)

    # Get all submitted certificates
    certs_query = select(SubmittedCertificate).where(
        SubmittedCertificate.form_verification_id == form_verification.id
    )
    result = await db.execute(certs_query)
    submitted_certs = result.scalars().all()

    return submitted_certs


# ========================
# Mark Student as Provisionally Allotted
# ========================


@verification_router.post(
    "/{student_id}/mark-provisionally-allotted",
    response_model=AdmissionFormVerificationResponse,
    name="Mark Provisionally Allotted",
)
async def mark_provisionally_allotted(
    student_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Mark student as provisionally allotted after all certificates are received and verified.
    This is done by the Form Verification Team.
    """
    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Get student
    student_query = select(AdmissionStudent).where(
        AdmissionStudent.id == student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Get form verification record
    fv_query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(fv_query)
    form_verification = result.scalar_one_or_none()

    if not form_verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found",
        )

    # Check if all mandatory certificates are received
    required_certs_query = select(DocumentType).where(
        and_(
            DocumentType.is_mandatory == True,
            DocumentType.is_active == True,
        )
    )
    result = await db.execute(required_certs_query)
    required_certs = result.scalars().all()

    # Get submitted certificates
    submitted_query = select(SubmittedCertificate).where(
        SubmittedCertificate.form_verification_id == form_verification.id
    )
    result = await db.execute(submitted_query)
    submitted_certs = result.scalars().all()

    submitted_cert_ids = set(sc.document_type_id for sc in submitted_certs if sc.is_received)

    # Check if all mandatory certificates are received
    for cert in required_certs:
        if cert.id not in submitted_cert_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mandatory certificate '{cert.name}' is not received",
            )

    # Update status
    form_verification.provisionally_allotted = True
    form_verification.provisionally_allotted_at = datetime.utcnow()
    form_verification.provisionally_allotted_by = user_id
    form_verification.status = VerificationStatusEnum.PROVISIONALLY_ALLOTTED

    # Update student status
    from common.models.admission.admission_entry import AdmissionStatusEnum
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED

    # Lock student's final fee structure at provisional allotment stage.
    try:
        from apps.billing.services import billing_service

        await billing_service.lock_student_fee_structure(
            db,
            student.id,
            locked_by=user_id,
        )
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fee structure lock failed: {exc}",
        )

    await _safe_commit(db)
    await db.refresh(form_verification)

    return form_verification


# ========================
# Update Submitted Certificate Verification Status
# ========================


@verification_router.patch(
    "/{student_id}/submitted-certificates/{submitted_certificate_id}/verify",
    response_model=SubmittedCertificateResponse,
    name="Verify Submitted Certificate",
)


async def verify_submitted_certificate(
    student_id: UUID,
    submitted_certificate_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update the verification status of a submitted certificate.
    """
    # Parse body which may be either flat {is_verified, is_received, remarks}
    # or wrapped { scope: {...}, data: {...} }
    try:
        raw = await request.json()
    except Exception:
        raw = {}

    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        payload = raw["data"]
    else:
        payload = raw or {}

    try:
        data = SubmittedCertificateUpdate(**payload)
    except ValidationError as ve:
        raise HTTPException(status_code=422, detail=jsonable_encoder(ve.errors()))

    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    # Get form verification for student
    fv_query = select(AdmissionFormVerification).where(
        AdmissionFormVerification.student_id == student_id
    )
    result = await db.execute(fv_query)
    form_verification = result.scalar_one_or_none()

    if not form_verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form verification record not found",
        )

    # Get the submitted certificate
    cert_query = select(SubmittedCertificate).where(
        and_(
            SubmittedCertificate.id == submitted_certificate_id,
            SubmittedCertificate.form_verification_id == form_verification.id,
        )
    )
    result = await db.execute(cert_query)
    submitted_cert = result.scalar_one_or_none()

    if not submitted_cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitted certificate not found",
        )

    # Update the certificate status
    if data.is_verified is not None:
        submitted_cert.is_verified = data.is_verified
        if data.is_verified:
            submitted_cert.verified_at = datetime.utcnow()
            submitted_cert.verified_by = user_id

    if data.is_received is not None:
        submitted_cert.is_received = data.is_received

    if data.remarks is not None:
        submitted_cert.remarks = data.remarks

    await _safe_commit(db)
    await db.refresh(submitted_cert)

    return submitted_cert


add_pagination(verification_router)
