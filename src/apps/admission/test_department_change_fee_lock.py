import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from fastapi import HTTPException

from apps.admission.department_change_routers import (
    create_department_change_request,
    approve_department_change_request,
)
from common.schemas.admission.department_change import (
    DepartmentChangeRequestCreate,
    ApproveRejectRequest,
)
from common.models.admission.admission_entry import AdmissionStatusEnum
from common.models.admission.department_change import DepartmentChangeStatusEnum


class MockResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_create_department_change_rejected_when_fee_structure_locked():
    db = AsyncMock()
    student = MagicMock()
    student.id = uuid4()
    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED
    student.is_fee_structure_locked = True

    db.execute = AsyncMock(return_value=MockResult(student))

    payload = DepartmentChangeRequestCreate(
        student_id=student.id,
        current_department_id=uuid4(),
        requested_department_id=uuid4(),
        reason="Need to switch to preferred stream",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "apps.admission.department_change_routers.get_user_id",
            AsyncMock(return_value=uuid4()),
        )
        with pytest.raises(HTTPException) as exc:
            await create_department_change_request(
                data=payload,
                request=MagicMock(),
                db=db,
            )

    assert exc.value.status_code == 400
    assert "fee structure is locked" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_approve_department_change_rejected_when_fee_structure_locked():
    db = AsyncMock()
    student_id = uuid4()

    change_request = MagicMock()
    change_request.id = uuid4()
    change_request.student_id = student_id
    change_request.status = DepartmentChangeStatusEnum.PENDING

    student = MagicMock()
    student.id = student_id
    student.is_fee_structure_locked = True

    db.execute = AsyncMock(
        side_effect=[MockResult(change_request), MockResult(student)]
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "apps.admission.department_change_routers.get_user_id",
            AsyncMock(return_value=uuid4()),
        )
        with pytest.raises(HTTPException) as exc:
            await approve_department_change_request(
                request_id=change_request.id,
                data=ApproveRejectRequest(remarks="approved"),
                request=MagicMock(),
                db=db,
            )

    assert exc.value.status_code == 400
    assert "fee structure is locked" in exc.value.detail.lower()
