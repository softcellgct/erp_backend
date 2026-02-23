import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from apps.billing.services import BillingService
from common.models.billing.financial_year import FinancialYear


@pytest.mark.asyncio
async def test_set_active_financial_year_deactivates_others_and_activates_target():
    # Arrange
    inst_id = uuid.uuid4()
    fy = FinancialYear(name="FY2025", start_date=None, end_date=None, active=False)
    fy.id = uuid.uuid4()
    # attach institution_id dynamically in case model doesn't declare it
    fy.institution_id = inst_id

    # Mock DB session
    db = MagicMock()
    # First execute (select) should return a result with scalar_one_or_none -> fy
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = fy
    # For update execute (deactivate others) we just return a dummy
    update_result = MagicMock()

    # db.execute is async
    async def execute_side_effect(stmt):
        # On first call return select_result, else return update_result
        if not hasattr(execute_side_effect, "called"):
            execute_side_effect.called = 1
            return select_result
        return update_result

    db.execute = AsyncMock(side_effect=execute_side_effect)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = BillingService()

    # Act
    res = await service.set_active_financial_year(db, str(fy.id))

    # Assert
    assert fy.active is True
    db.execute.assert_called()
    db.commit.assert_awaited()
    db.refresh.assert_awaited_with(fy)


@pytest.mark.asyncio
async def test_set_active_financial_year_raises_if_not_found():
    db = MagicMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=select_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = BillingService()

    with pytest.raises(ValueError):
        await service.set_active_financial_year(db, str(uuid.uuid4()))
