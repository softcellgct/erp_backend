from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from common.models.billing.concession_rule import ConcessionRule
from common.models.admission.admission_entry import AdmissionStudentPreviousAcademicDetails
from common.models.billing.concession import Concession

async def evaluate_concessions_for_student(db: AsyncSession, student_id: UUID, institution_id: UUID):
    # 1. Fetch student's academic metrics
    acad_stmt = select(AdmissionStudentPreviousAcademicDetails).where(
        AdmissionStudentPreviousAcademicDetails.admission_student_id == student_id
    )
    acad_result = await db.execute(acad_stmt)
    academics = acad_result.scalars().first()

    if not academics:
        return

    # Collect available metrics
    metrics = {
        "cutoff_marks": academics.hsc_cutoff_mark or Decimal("0"),
        "sslc_total": academics.sslc_total_mark_secured or Decimal("0"),
        # More metrics can be mapped here
    }

    # 2. Fetch active rules for the institution
    rule_stmt = select(ConcessionRule).where(
        ConcessionRule.institution_id == institution_id,
        ConcessionRule.is_active == True
    )
    rule_result = await db.execute(rule_stmt)
    rules = rule_result.scalars().all()

    applied_rules = []

    for rule in rules:
        val = metrics.get(rule.condition_metric)
        if val is None:
            continue

        matched = False
        if rule.operator == ">" and val > rule.threshold_value:
            matched = True
        elif rule.operator == ">=" and val >= rule.threshold_value:
            matched = True
        elif rule.operator == "<" and val < rule.threshold_value:
            matched = True
        elif rule.operator == "<=" and val <= rule.threshold_value:
            matched = True
        elif rule.operator == "==" and val == rule.threshold_value:
            matched = True

        if matched:
            # Check if this rule is already applied
            existing_stmt = select(Concession).where(
                Concession.student_id == student_id,
                Concession.meta.contains({"rule_id": str(rule.id)})
            )
            existing_res = await db.execute(existing_stmt)
            if not existing_res.scalars().first():
                # Apply concession automatically
                new_conc = Concession(
                    student_id=student_id,
                    institution_id=institution_id,
                    fee_head_id=rule.target_fee_head_id,
                    percent=rule.concession_percent,
                    status="approved",
                    meta={"rule_id": str(rule.id), "auto_applied": True, "metric_val": str(val)}
                )
                db.add(new_conc)
                applied_rules.append(rule)

    if applied_rules:
        await db.commit()

