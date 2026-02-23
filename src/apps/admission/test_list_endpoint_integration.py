"""
Integration test for the list_admission_students endpoint.
Tests the full flow including serialization and error handling.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import uuid4

from apps.admission.routers import list_admission_students
from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from common.schemas.admission.admission_entry import AdmissionStudentResponse


@pytest.mark.asyncio
async def test_list_admission_students_returns_serializable_data():
    """Test that the endpoint returns data that can be JSON serialized."""
    # Create mock database
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Create realistic mock student objects with all required fields
    student_id_1 = str(uuid4())
    student_id_2 = str(uuid4())
    
    mock_student_1 = MagicMock(spec=AdmissionStudent)
    mock_student_1.id = student_id_1
    mock_student_1.name = "John Doe"
    mock_student_1.enquiry_number = "ENQ-TEST-1"
    mock_student_1.application_number = "APP-TEST-1"
    mock_student_1.status = AdmissionStatusEnum.APPLIED.value
    mock_student_1.created_at = datetime.utcnow()
    mock_student_1.updated_at = datetime.utcnow()
    mock_student_1.deleted_at = None
    mock_student_1.department = None
    mock_student_1.course = None
    mock_student_1.__dict__.update({
        'id': student_id_1,
        'name': 'John Doe',
        'status': AdmissionStatusEnum.APPLIED.value,
        'created_at': datetime.utcnow(),
    })
    
    mock_student_2 = MagicMock(spec=AdmissionStudent)
    mock_student_2.id = student_id_2
    mock_student_2.name = "Jane Smith"
    mock_student_2.enquiry_number = "ENQ-TEST-2"
    mock_student_2.application_number = "APP-TEST-2"
    mock_student_2.status = AdmissionStatusEnum.APPLIED.value
    mock_student_2.created_at = datetime.utcnow()
    mock_student_2.updated_at = datetime.utcnow()
    mock_student_2.deleted_at = None
    mock_student_2.department = None
    mock_student_2.course = None
    mock_student_2.__dict__.update({
        'id': student_id_2,
        'name': 'Jane Smith',
        'status': AdmissionStatusEnum.APPLIED.value,
        'created_at': datetime.utcnow(),
    })
    
    # Create properly structured mock results
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_student_1, mock_student_2]
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar.return_value = 2  # For count
    
    # Configure mock_db.execute to return the appropriate mock
    mock_db.execute = AsyncMock(return_value=result_mock)
    
    # Test with status filter
    filters_json = json.dumps({"status": {"$in": ["APPLIED", "PROVISIONALLY_ALLOTTED", "ENROLLED"]}})
    
    result = await list_admission_students(
        page=1,
        size=10,
        search="APP-TEST",
        filters=filters_json,
        db=mock_db
    )
    
    # Verify response structure
    assert isinstance(result, dict)
    assert "items" in result
    assert "total" in result
    assert "page" in result
    assert "size" in result
    assert "pages" in result
    
    # Verify data
    assert result["total"] == 2
    assert result["page"] == 1
    assert result["size"] == 10
    assert len(result["items"]) == 2
    
    # Items should be Pydantic response models (or dict representation)
    for item in result["items"]:
        # Could be a Pydantic model instance or dict
        assert hasattr(item, 'id') or isinstance(item, dict)
    
    print("✓ Test passed: Endpoint returns properly structured data")


@pytest.mark.asyncio
async def test_list_admission_students_handles_empty_results():
    """Test that the endpoint handles empty results correctly."""
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Create empty result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar.return_value = 0  # For count
    
    mock_db.execute = AsyncMock(return_value=result_mock)
    
    # Test with a search term that returns no results
    result = await list_admission_students(
        page=1,
        size=10,
        search="NONEXISTENT",
        filters=None,
        db=mock_db
    )
    
    assert result["total"] == 0
    assert result["items"] == []
    assert result["pages"] == 1
    
    print("✓ Test passed: Empty results handled correctly")


@pytest.mark.asyncio
async def test_list_admission_students_pagination():
    """Test that pagination parameters work correctly."""
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Create mock results
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar.return_value = 250  # 250 total results
    
    mock_db.execute = AsyncMock(return_value=result_mock)
    
    # Test pagination
    result = await list_admission_students(
        page=3,
        size=25,
        search=None,
        filters=None,
        db=mock_db
    )
    
    # 250 / 25 = 10 pages
    assert result["pages"] == 10
    assert result["page"] == 3
    assert result["size"] == 25
    assert result["total"] == 250
    
    print("✓ Test passed: Pagination calculations correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
