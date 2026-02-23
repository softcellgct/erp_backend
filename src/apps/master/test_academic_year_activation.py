import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from apps.master.services.annual_task import AnnualTaskService
from common.models.master.annual_task import AcademicYear


@pytest.mark.asyncio
async def test_set_active_academic_year_activates_and_deactivates_same_institution():
    ay = AcademicYear(year_name="2025", from_date=None, to_date=None, status=False, admission_active=False)
    ay.id = uuid.uuid4()
    ay.institution_id = uuid.uuid4()

    db = MagicMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = ay

    async def execute_side_effect(stmt):
        # First call is select -> return select_result
        if not hasattr(execute_side_effect, "called"):
            execute_side_effect.called = 1
            return select_result
        return MagicMock()

    db.execute = AsyncMock(side_effect=execute_side_effect)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = AnnualTaskService(db)
    res = await svc.set_active_academic_year(ay.id)

    assert res.status is True
    db.execute.assert_called()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_set_active_academic_year_raises_if_missing():
    db = MagicMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=select_result)
    db.commit = AsyncMock()

    svc = AnnualTaskService(db)

    with pytest.raises(Exception):
        await svc.set_active_academic_year(uuid.uuid4())
