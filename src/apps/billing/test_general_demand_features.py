import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.billing.services import BillingService
from common.schemas.billing.demand_schemas import GeneralDemandCreateRequest


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values

    def first(self):
        return self._values[0] if self._values else None


class _FakeResult:
    def __init__(self, scalar_one_or_none=None, scalars_values=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_values = scalars_values if scalars_values is not None else []

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return _FakeScalarResult(self._scalars_values)


def _student(student_id, app_no=None, roll_no=None, name="Student A"):
    return SimpleNamespace(
        id=student_id,
        name=name,
        application_number=app_no,
        roll_number=roll_no,
        department=SimpleNamespace(name="CSE"),
        course=SimpleNamespace(title="B.E CSE"),
        year="1",
    )


@pytest.mark.asyncio
async def test_resolve_students_by_identifiers_matches_roll_number_case_insensitive():
    service = BillingService()
    institution_id = uuid.uuid4()
    sid = uuid.uuid4()
    student = _student(sid, app_no="APP-001", roll_no="RN001")

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeResult(scalars_values=[student]))

    result = await service.resolve_students_by_identifiers(
        db=db,
        institution_id=institution_id,
        identifiers=[" rn001 "],
    )

    assert len(result["matched_students"]) == 1
    assert result["matched_students"][0]["id"] == sid
    assert result["unmatched_identifiers"] == []


@pytest.mark.asyncio
async def test_resolve_students_by_identifiers_reports_unmatched_values():
    service = BillingService()
    institution_id = uuid.uuid4()
    sid = uuid.uuid4()
    student = _student(sid, app_no="APP-001", roll_no="RN001")

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeResult(scalars_values=[student]))

    result = await service.resolve_students_by_identifiers(
        db=db,
        institution_id=institution_id,
        identifiers=["APP-001", "MISSING-123"],
    )

    assert len(result["matched_students"]) == 1
    assert result["unmatched_identifiers"] == ["MISSING-123"]


@pytest.mark.asyncio
async def test_resolve_students_by_identifiers_raises_on_conflicting_identifier():
    service = BillingService()
    institution_id = uuid.uuid4()
    student_one = _student(uuid.uuid4(), app_no="APP-CONFLICT", roll_no="R1", name="A")
    student_two = _student(uuid.uuid4(), app_no="APP-CONFLICT", roll_no="R2", name="B")

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=_FakeResult(scalars_values=[student_one, student_two])
    )

    with pytest.raises(ValueError, match="matches multiple students"):
        await service.resolve_students_by_identifiers(
            db=db,
            institution_id=institution_id,
            identifiers=["APP-CONFLICT"],
        )


@pytest.mark.asyncio
async def test_derive_general_demand_amount_uses_fee_structure_year_mapping():
    service = BillingService()
    fee_head_id = uuid.uuid4()
    fee_sub_head_id = uuid.uuid4()
    item_id = uuid.uuid4()

    item = SimpleNamespace(
        id=item_id,
        fee_head_id=fee_head_id,
        fee_sub_head_id=fee_sub_head_id,
        amount_by_year={"2": 2500},
        amount=0,
    )
    fee_structure = SimpleNamespace(items=[item])

    amount, matched_item_id = await service._derive_general_demand_amount(
        fee_structure=fee_structure,
        fee_head_id=fee_head_id,
        fee_sub_head_id=fee_sub_head_id,
        year="2",
    )

    assert amount == 2500
    assert matched_item_id == item_id


@pytest.mark.asyncio
async def test_create_general_demand_skips_duplicates_when_enabled():
    service = BillingService()
    institution_id = uuid.uuid4()
    fee_structure_id = uuid.uuid4()
    fee_head_id = uuid.uuid4()
    fee_sub_head_id = uuid.uuid4()
    sid_from_identifier = uuid.uuid4()
    sid_explicit = uuid.uuid4()
    fee_item_id = uuid.uuid4()

    fee_structure = SimpleNamespace(
        id=fee_structure_id,
        institution_id=institution_id,
        items=[
            SimpleNamespace(
                id=fee_item_id,
                fee_head_id=fee_head_id,
                fee_sub_head_id=fee_sub_head_id,
                amount_by_year={"1": 1000},
                amount=1000,
            )
        ],
    )
    fee_head = SimpleNamespace(id=fee_head_id, institution_id=institution_id, name="Tuition")
    fee_sub_head = SimpleNamespace(
        id=fee_sub_head_id,
        institution_id=institution_id,
        fee_head_id=fee_head_id,
        name="Semester 1",
    )
    resolved_student = _student(
        sid_from_identifier,
        app_no="APP-001",
        roll_no="RN001",
    )

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult(scalar_one_or_none=fee_structure),  # fee structure
            _FakeResult(scalar_one_or_none=fee_head),  # fee head
            _FakeResult(scalar_one_or_none=fee_sub_head),  # fee subhead
            _FakeResult(scalars_values=[resolved_student]),  # identifier resolve
            _FakeResult(scalars_values=[sid_from_identifier, sid_explicit]),  # student validation
            _FakeResult(scalars_values=[sid_from_identifier]),  # existing duplicate
        ]
    )
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    payload = GeneralDemandCreateRequest(
        institution_id=institution_id,
        student_ids=[sid_explicit],
        identifiers=["APP-001"],
        fee_structure_id=fee_structure_id,
        year="1",
        fee_head_id=fee_head_id,
        fee_sub_head_id=fee_sub_head_id,
        amount=1000,
        description="General Demand",
        avoid_duplicates=True,
    )

    result = await service.create_general_demand(db=db, payload=payload)

    assert result["resolved_student_count"] == 2
    assert result["created_count"] == 1
    assert result["skipped_count"] == 1
    assert result["amount_used"] == 1000.0
    assert result["unmatched_identifiers"] == []
