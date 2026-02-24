import uuid
from datetime import datetime

from apps.billing.services import BillingService


def test_normalize_demand_filters_serializes_uuid_and_ignores_empty_values():
    service = BillingService()
    department_id = uuid.uuid4()
    student_id = uuid.uuid4()

    filters = {
        "department_id": department_id,
        "gender": "",
        "batches": ["1", "", None, "2"],
        "apply_to_students": [student_id, ""],
        "meta": {},
    }

    normalized = service._normalize_demand_filters(filters)

    assert normalized["department_id"] == str(department_id)
    assert normalized["batches"] == ["1", "2"]
    assert normalized["apply_to_students"] == [str(student_id)]
    assert "gender" not in normalized
    assert "meta" not in normalized


def test_finalize_ledger_entries_calculates_opening_running_and_closing_balance():
    service = BillingService()

    entries = [
        {
            "entry_date": datetime(2026, 1, 1, 10, 0, 0),
            "entry_type": "demand",
            "source": "demand_item",
            "source_id": uuid.uuid4(),
            "debit": 1000,
            "credit": 0,
        },
        {
            "entry_date": datetime(2026, 1, 5, 10, 0, 0),
            "entry_type": "payment",
            "source": "payment",
            "source_id": uuid.uuid4(),
            "debit": 0,
            "credit": 300,
        },
        {
            "entry_date": datetime(2026, 1, 10, 10, 0, 0),
            "entry_type": "demand",
            "source": "demand_item",
            "source_id": uuid.uuid4(),
            "debit": 500,
            "credit": 0,
        },
        {
            "entry_date": datetime(2026, 1, 12, 10, 0, 0),
            "entry_type": "payment",
            "source": "payment",
            "source_id": uuid.uuid4(),
            "debit": 0,
            "credit": 200,
        },
    ]

    summary = service._finalize_ledger_entries(
        entries=entries,
        from_dt=datetime(2026, 1, 6, 0, 0, 0),
        to_dt=datetime(2026, 1, 31, 23, 59, 59),
    )

    assert summary["opening_balance"] == 700
    assert summary["total_debit"] == 500
    assert summary["total_credit"] == 200
    assert summary["closing_balance"] == 1000
    assert len(summary["entries"]) == 2
    assert summary["entries"][0]["running_balance"] == 1200
    assert summary["entries"][1]["running_balance"] == 1000
