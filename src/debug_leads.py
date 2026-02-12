
import asyncio
import sys
import os

# Adjust path to include backend directory
sys.path.append(os.path.abspath("/home/prithivi/ERP/backend/src"))

from components.db.db import db_engine
from sqlalchemy import select, text
from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

async def check_students():
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        print("Checking Admission Students...")
        
        # 1. Check all students and their statuses
        stmt = select(AdmissionStudent.id, AdmissionStudent.name, AdmissionStudent.status, AdmissionStudent.enquiry_number)
        result = await session.execute(stmt)
        students = result.all()
        
        print(f"Found {len(students)} students total.")
        for s in students:
            print(f"Name: {s.name}, Status: '{s.status}', Status Enum Match: {s.status == AdmissionStatusEnum.FEE_PENDING}")

        # 2. Check explicitly for what the filtered query would find
        print("\nChecking logic for get_lead_students...")
        statuses = [
            AdmissionStatusEnum.APPLIED,
            AdmissionStatusEnum.DOCUMENTS_PENDING,
            AdmissionStatusEnum.DOCUMENTS_VERIFIED,
            AdmissionStatusEnum.FEE_PENDING
        ]
        stmt_filtered = select(AdmissionStudent).where(AdmissionStudent.status.in_(statuses))
        res_filtered = await session.execute(stmt_filtered)
        filtered_students = res_filtered.scalars().all()
        print(f"Query found {len(filtered_students)} students matching the filter.")
        for s in filtered_students:
             print(f" - {s.name} ({s.status})")

        # 3. Check Invoice/Payment Logic
        print("\nChecking Application Fee payments...")
        # (Simplified check)
        stmt_invoices = text("SELECT student_id, status FROM invoices")
        res_invoices = await session.execute(stmt_invoices)
        for row in res_invoices:
             print(f"Invoice for Student ID {row[0]}: Status {row[1]}")

if __name__ == "__main__":
    asyncio.run(check_students())
