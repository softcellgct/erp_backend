"""
OCR Router for document processing
Handles file uploads and OCR extraction for admission documents
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import io

from components.ocr.extractor import OCRExtractor, DocumentType
from components.db.db import get_db_session
from components.generator.utils.get_user_from_request import get_user_id

logger = logging.getLogger(__name__)

ocr_router = APIRouter(
    prefix="/ocr",
    tags=["OCR - Document Processing"],
    responses={
        404: {"description": "Not found"},
        400: {"description": "Bad request"},
    }
)


@ocr_router.post("/extract-document")
async def extract_document(
    file: UploadFile = File(...),
    document_type: str = None,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Upload a document image and extract structured data via OCR
    
    Args:
        file: Image file (JPG, PNG, PDF)
        document_type: Optional hint - 'id_card', 'mark_sheet', 'certificate'
        
    Returns:
        {
            "success": bool,
            "document_type": str,
            "confidence": float (0-1),
            "personal_data": {name, dob, gender, mobile, address, aadhaar, pan},
            "academic_data": {register_number, board, year_of_passing, marks, percentage, subjects},
            "address_data": {door_no, street, village, taluk, district, state, pincode},
            "raw_text": str (full OCR text),
            "error": str (if any)
        }
    """
    try:
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.gif', '.bmp'}
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Process image
        logger.info(f"Processing OCR for file: {file.filename} (user: {user_id})")
        result = OCRExtractor.extract_all_data(content, doc_type=document_type)
        
        # Filter out empty nested objects
        result['personal_data'] = {k: v for k, v in result['personal_data'].items() if v}
        result['academic_data'] = {k: v for k, v in result['academic_data'].items() if v or k == 'subjects'}
        
        return JSONResponse(
            status_code=200 if not result.get('error') else 206,  # 206 = Partial Content
            content={
                "success": True if not result.get('error') else False,
                "message": "Document processed successfully" if not result.get('error') else f"Partial extraction: {result.get('error')}",
                "data": result
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )


@ocr_router.post("/validate-extraction")
async def validate_extraction(
    extraction_data: dict,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Validate and confirm OCR extracted data
    User reviews extracted values and confirms what should be used
    
    Args:
        extraction_data: {
            "personal_data": {...validated fields...},
            "academic_data": {...validated fields...},
            "address_data": {...validated fields...}
        }
        
    Returns:
        {"success": bool, "processed_data": {...}}
    """
    try:
        # TODO: Add validation rules per field
        # Example: Name > 3 chars, DOB is valid date format, etc.
        
        processed = {
            'personal_data': extraction_data.get('personal_data', {}),
            'academic_data': extraction_data.get('academic_data', {}),
            'address_data': extraction_data.get('address_data', {}),
        }
        
        return {
            "success": True,
            "processed_data": processed
        }
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@ocr_router.post("/detect-type")
async def detect_document_type(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
):
    """
    Quickly detect document type from image without full extraction
    
    Returns:
        {"document_type": "id_card|mark_sheet|certificate|unknown", "confidence": float}
    """
    try:
        content = await file.read()
        text = OCRExtractor.extract_text_from_image(content)
        doc_type = OCRExtractor.detect_document_type(text)
        
        return {
            "document_type": doc_type,
            "confidence": 0.7 if doc_type != DocumentType.UNKNOWN else 0.3
        }
    except Exception as e:
        logger.error(f"Document type detection error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
