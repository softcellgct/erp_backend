import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Prevent loguru multiprocessing queue setup during test import.
class _DummyLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("logs.logging", types.SimpleNamespace(logger=_DummyLogger()))

from apps.gate.services import AdmissionVisitorCRUD
from common.models.gate.visitor_model import ReferenceType, VisitStatus
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorPassOutRequest,
    AdmissionVisitorReportSummary,
)


@pytest.mark.asyncio
async def test_pass_out_success_updates_visitor():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()
    db.add = MagicMock()

    visitor = SimpleNamespace(
        id="v1",
        visit_status=VisitStatus.CHECKED_IN,
        check_in_time=datetime.now(timezone.utc) - timedelta(hours=2),
        check_out_time=None,
        check_out_remarks=None,
    )

    crud.get_one = AsyncMock(return_value=visitor)
    db.refresh = AsyncMock(return_value=None)
    payload = AdmissionVisitorPassOutRequest(remarks="left campus")

    updated, already_checked_out = await crud.pass_out(db, visitor.id, payload)

    assert already_checked_out is False
    assert updated.visit_status == VisitStatus.CHECKED_OUT
    assert updated.check_out_time is not None
    assert updated.check_out_remarks == "left campus"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_pass_out_is_idempotent_for_checked_out_visitor():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()
    db.add = MagicMock()

    visitor = SimpleNamespace(
        id="v2",
        visit_status=VisitStatus.CHECKED_OUT,
        check_in_time=datetime.now(timezone.utc) - timedelta(hours=3),
        check_out_time=datetime.now(timezone.utc) - timedelta(hours=1),
        check_out_remarks="already done",
    )

    crud.get_one = AsyncMock(return_value=visitor)
    payload = AdmissionVisitorPassOutRequest()

    updated, already_checked_out = await crud.pass_out(db, visitor.id, payload)

    assert already_checked_out is True
    assert updated is visitor
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_pass_out_rejects_checkout_before_checkin():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()
    db.add = MagicMock()

    check_in_time = datetime.now(timezone.utc)
    visitor = SimpleNamespace(
        id="v3",
        visit_status=VisitStatus.CHECKED_IN,
        check_in_time=check_in_time,
        check_out_time=None,
        check_out_remarks=None,
    )
    crud.get_one = AsyncMock(return_value=visitor)

    payload = AdmissionVisitorPassOutRequest(
        check_out_time=check_in_time - timedelta(minutes=1)
    )

    with pytest.raises(ValueError, match="check_out_time cannot be earlier"):
        await crud.pass_out(db, visitor.id, payload)


@pytest.mark.asyncio
async def test_get_by_gate_pass_no_strips_input():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()

    expected_visitor = SimpleNamespace(id="visitor-id")
    scalar_result = MagicMock()
    scalar_result.first.return_value = expected_visitor
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalar_result
    db.execute = AsyncMock(return_value=execute_result)

    visitor = await crud.get_by_gate_pass_no(db, " 20260222/001 ")
    assert visitor is expected_visitor

    stmt = db.execute.call_args[0][0]
    compiled = stmt.compile()
    assert "20260222/001" in compiled.params.values()
    assert " 20260222/001 " not in compiled.params.values()


@pytest.mark.asyncio
async def test_export_report_csv_returns_expected_headers_and_row():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()

    now = datetime(2026, 2, 22, 9, 30, tzinfo=timezone.utc)
    visitor = SimpleNamespace(
        id=uuid4(),
        gate_pass_no="20260222/001",
        student_name="Test Student",
        mobile_number="9999999999",
        parent_or_guardian_name="Parent Name",
        native_place="Salem",
        institution_id=uuid4(),
        reference_type=ReferenceType.STAFF,
        visit_status=VisitStatus.CHECKED_IN,
        check_in_time=now,
        check_out_time=None,
        check_out_remarks=None,
        created_at=now,
        updated_at=now,
    )
    execute_result = MagicMock()
    execute_result.all.return_value = [(visitor, "ERP College")]
    db.execute = AsyncMock(return_value=execute_result)

    csv_text, filename = await crud.export_report_csv(
        db,
        date_from=None,
        date_to=None,
        visit_status=None,
        institution_id=None,
        reference_type=None,
        search=None,
    )

    lines = csv_text.strip().splitlines()
    assert lines
    assert lines[0].startswith("gate_pass_no,student_name,mobile_number")
    assert "20260222/001" in csv_text
    assert "Test Student" in csv_text
    assert "checked_in" in csv_text
    assert filename.startswith("admission_visitor_reports_")
    assert filename.endswith(".csv")


@pytest.mark.asyncio
async def test_get_report_returns_items_with_summary_payload():
    crud = AdmissionVisitorCRUD()
    db = AsyncMock()

    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    visitor = SimpleNamespace(
        id=uuid4(),
        gate_pass_no="20260222/010",
        student_name="Report Student",
        mobile_number="8888888888",
        parent_or_guardian_name="Guardian",
        native_place="Coimbatore",
        institution_id=uuid4(),
        reference_type=ReferenceType.CONSULTANCY,
        visit_status=VisitStatus.CHECKED_OUT,
        check_in_time=now - timedelta(hours=1),
        check_out_time=now,
        check_out_remarks="Completed",
        created_at=now - timedelta(hours=1),
        updated_at=now,
    )
    execute_result = MagicMock()
    execute_result.all.return_value = [(visitor, "ERP Campus")]
    db.execute = AsyncMock(return_value=execute_result)

    crud._get_count = AsyncMock(return_value=1)
    crud._get_report_summary = AsyncMock(
        return_value=AdmissionVisitorReportSummary(
            total_entries=1,
            total_exits=1,
            inside_campus=0,
        )
    )

    payload = await crud.get_report(
        db,
        date_from=None,
        date_to=None,
        visit_status=None,
        institution_id=None,
        reference_type=None,
        search=None,
        page=1,
        size=20,
    )

    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["size"] == 20
    assert payload["pages"] == 1
    assert payload["summary"] == {
        "total_entries": 1,
        "total_exits": 1,
        "inside_campus": 0,
    }
    assert len(payload["items"]) == 1
    assert payload["items"][0]["gate_pass_no"] == "20260222/010"
