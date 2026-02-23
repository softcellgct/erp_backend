"""
Test the custom list_admission_students endpoint to ensure it handles
filtering and search without JSON column errors.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# Import the endpoint function
from apps.admission.routers import list_admission_students
from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum


@pytest.mark.asyncio
async def test_list_admission_students_with_status_filter():
    """Test that status filter works without triggering JSON column search."""
    # Create mock database
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock student objects
    mock_student_1 = MagicMock(spec=AdmissionStudent)
    mock_student_1.id = "test-id-1"
    mock_student_1.name = "John Doe"
    mock_student_1.status = AdmissionStatusEnum.APPLIED.value
    
    mock_student_2 = MagicMock(spec=AdmissionStudent)
    mock_student_2.id = "test-id-2"
    mock_student_2.name = "Jane Smith"
    mock_student_2.status = AdmissionStatusEnum.APPLIED.value
    
    # Create a properly structured mock result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_student_1, mock_student_2]
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar.return_value = 2  # For count
    
    # Configure mock_db.execute to return the appropriate mock
    mock_db.execute = AsyncMock(return_value=result_mock)
    
    # Test with status filter
    filters_json = json.dumps({"status": {"$in": ["APPLIED", "PROVISIONALLY_ALLOTTED", "ENROLLED"]}})
    
    try:
        result = await list_admission_students(
            page=1,
            size=50,
            search=None,
            filters=filters_json,
            db=mock_db
        )
        
        assert result is not None
        assert isinstance(result, dict)
        assert "items" in result
        assert "total" in result
        assert "page" in result
        print("✓ Test passed: Status filter works correctly")
        print(f"  Items: {len(result['items'])}, Total: {result['total']}")
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        raise


@pytest.mark.asyncio
async def test_list_admission_students_with_search():
    """Test that search works on safe fields without JSON column errors."""
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock student object
    mock_student = MagicMock(spec=AdmissionStudent)
    mock_student.id = "test-id-1"
    mock_student.name = "John Doe"
    mock_student.status = AdmissionStatusEnum.APPLIED.value
    
    # Create a properly structured mock result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_student]
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar.return_value = 1  # For count
    
    # Configure mock_db.execute to return the appropriate mock
    mock_db.execute = AsyncMock(return_value=result_mock)
    
    try:
        result = await list_admission_students(
            page=1,
            size=50,
            search="John",
            filters=None,
            db=mock_db
        )
        
        assert result is not None
        assert "items" in result
        assert result["total"] == 1
        print("✓ Test passed: Search on safe fields works correctly")
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
