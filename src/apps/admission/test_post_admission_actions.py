import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from uuid import uuid4

from apps.admission.routers import (
    assign_roll_number,
    assign_section,
    activate_sem1,
    update_course_and_fees,
    set_fee_structure_and_lock,
    bulk_update_admission_student_status,
)
from common.schemas.admission.admission_entry import (
    AssignRollNumberRequest,
    AssignSectionRequest,
    ActivateSem1Request,
    SetFeeStructureLockRequest,
    UpdateCourseRequest,
    BulkAdmissionStatusUpdateRequest,
)
from common.models.admission.admission_entry import AdmissionStatusEnum


class MockResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class MockListResult:
    def __init__(self, values):
        self._values = values

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    def scalars(self):
        return self._Scalars(self._values)


@pytest.mark.asyncio
async def test_assign_roll_number_success():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"
    student.institution_id = "inst-1"

    db.execute = AsyncMock(side_effect=[MockResult(student), MockResult(None)])

    result = await assign_roll_number(
        student_id="student-1",
        payload=AssignRollNumberRequest(roll_number="RN001"),
        db=db,
    )

    assert result is student
    assert student.roll_number == "RN001"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_roll_number_duplicate_rejected():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"
    student.institution_id = "inst-1"

    db.execute = AsyncMock(side_effect=[MockResult(student), MockResult("other-id")])

    with pytest.raises(HTTPException) as exc:
        await assign_roll_number(
            student_id="student-1",
            payload=AssignRollNumberRequest(roll_number="RN001"),
            db=db,
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_assign_section_success():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"

    db.execute = AsyncMock(return_value=MockResult(student))

    result = await assign_section(
        student_id="student-1",
        payload=AssignSectionRequest(section="A"),
        db=db,
    )

    assert result is student
    assert student.section == "A"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_activate_sem1_success():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"
    student.institution_id = "inst-1"
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value
    student.roll_number = None
    student.section = None

    db.execute = AsyncMock(side_effect=[MockResult(student), MockResult(None)])

    result = await activate_sem1(
        student_id="student-1",
        payload=ActivateSem1Request(roll_number="RN010", section="B"),
        db=db,
    )

    assert result is student
    assert student.status == AdmissionStatusEnum.ENROLLED.value
    assert student.current_semester == 1
    assert student.is_sem1_active is True
    assert student.roll_number == "RN010"
    assert student.section == "B"


@pytest.mark.asyncio
async def test_activate_sem1_invalid_status_rejected():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"
    student.status = AdmissionStatusEnum.APPLIED.value

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.raises(HTTPException) as exc:
        await activate_sem1(
            student_id="student-1",
            payload=ActivateSem1Request(),
            db=db,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_course_rejected_when_fee_structure_locked():
    db = AsyncMock()
    student = MagicMock()
    student.id = uuid4()
    student.is_fee_structure_locked = True

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.raises(HTTPException) as exc:
        await update_course_and_fees(
            student_id=student.id,
            payload=UpdateCourseRequest(
                course_id=uuid4(),
                fee_structure_id=uuid4(),
                department_id=uuid4(),
            ),
            db=db,
        )

    assert exc.value.status_code == 400
    assert "locked" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_bulk_provisionally_allot_locks_fee_structure():
    db = AsyncMock()
    student = MagicMock()
    student_id = uuid4()
    student.id = student_id
    student.status = AdmissionStatusEnum.APPLIED.value

    db.execute = AsyncMock(return_value=MockListResult([student]))

    with pytest.MonkeyPatch.context() as mp:
        lock_mock = AsyncMock(return_value=uuid4())
        mp.setattr("apps.admission.routers.billing_service.lock_student_fee_structure", lock_mock)

        response = await bulk_update_admission_student_status(
            payload=BulkAdmissionStatusUpdateRequest(
                student_ids=[student_id],
                new_status=AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
            ),
            db=db,
        )

    assert response.updated_count == 1
    assert response.failed_count == 0
    assert student.status == AdmissionStatusEnum.PROVISIONALLY_ALLOTTED
    lock_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_provisionally_allot_fails_when_fee_lock_fails():
    db = AsyncMock()
    student = MagicMock()
    student_id = uuid4()
    student.id = student_id
    student.status = AdmissionStatusEnum.APPLIED.value

    db.execute = AsyncMock(return_value=MockListResult([student]))

    with pytest.MonkeyPatch.context() as mp:
        lock_mock = AsyncMock(side_effect=ValueError("No matching fee structure"))
        mp.setattr("apps.admission.routers.billing_service.lock_student_fee_structure", lock_mock)

        response = await bulk_update_admission_student_status(
            payload=BulkAdmissionStatusUpdateRequest(
                student_ids=[student_id],
                new_status=AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
            ),
            db=db,
        )

    assert response.updated_count == 0
    assert response.failed_count == 1
    assert "lock failed" in (response.results[0].message or "").lower()
    assert student.status == AdmissionStatusEnum.APPLIED.value
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_fee_structure_and_lock_success():
    db = AsyncMock()
    student = MagicMock()
    student_id = uuid4()
    student.id = student_id
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value
    student.is_fee_structure_locked = False
    student.fee_structure_id = None

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.MonkeyPatch.context() as mp:
        lock_mock = AsyncMock(return_value=uuid4())
        get_user_mock = AsyncMock(return_value=uuid4())
        mp.setattr("apps.admission.routers.billing_service.lock_student_fee_structure", lock_mock)
        mp.setattr("apps.admission.routers.get_user_id", get_user_mock)

        response = await set_fee_structure_and_lock(
            student_id=student_id,
            payload=SetFeeStructureLockRequest(fee_structure_id=uuid4()),
            request=MagicMock(),
            db=db,
        )

    assert response is student
    lock_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_fee_structure_and_lock_allows_applied_status():
    db = AsyncMock()
    student = MagicMock()
    student_id = uuid4()
    student.id = student_id
    student.status = AdmissionStatusEnum.APPLIED.value
    student.is_fee_structure_locked = False
    student.fee_structure_id = None

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.MonkeyPatch.context() as mp:
        lock_mock = AsyncMock(return_value=uuid4())
        get_user_mock = AsyncMock(return_value=uuid4())
        mp.setattr("apps.admission.routers.billing_service.lock_student_fee_structure", lock_mock)
        mp.setattr("apps.admission.routers.get_user_id", get_user_mock)

        response = await set_fee_structure_and_lock(
            student_id=student_id,
            payload=SetFeeStructureLockRequest(fee_structure_id=uuid4()),
            request=MagicMock(),
            db=db,
        )

    assert response is student
    lock_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_fee_structure_and_lock_rejected_when_already_locked():
    db = AsyncMock()
    student = MagicMock()
    student_id = uuid4()
    student.id = student_id
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value
    student.is_fee_structure_locked = True
    student.fee_structure_id = uuid4()

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.raises(HTTPException) as exc:
        await set_fee_structure_and_lock(
            student_id=student_id,
            payload=SetFeeStructureLockRequest(fee_structure_id=uuid4()),
            request=MagicMock(),
            db=db,
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_activate_sem1_missing_roll_or_section_rejected():
    db = AsyncMock()
    student = MagicMock()
    student.id = "student-1"
    student.institution_id = "inst-1"
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value
    student.roll_number = None
    student.section = None

    db.execute = AsyncMock(return_value=MockResult(student))

    with pytest.raises(HTTPException) as exc:
        await activate_sem1(
            student_id="student-1",
            payload=ActivateSem1Request(),
            db=db,
        )

    assert exc.value.status_code == 400
