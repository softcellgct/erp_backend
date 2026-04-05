import re

with open('src/apps/admission/routers.py', 'r') as f:
    text = f.read()

def replacer(m):
    return '''    # Paginated data
    offset = (page - 1) * size
    stmt = stmt.options(selectinload(AdmissionStudent.personal_details), selectinload(AdmissionStudent.program_details), selectinload(AdmissionStudent.gate_entry)).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
    result = await db.execute(stmt)
    students = result.scalars().all()

    items = [
        {
            "id": str(s.id),
            "enquiry_number": s.enquiry_number,
            "name": s.personal_details.name if s.personal_details else None,
            "mobile": s.personal_details.student_mobile if s.personal_details else None,
            "parent_name": s.personal_details.father_name if s.personal_details else None,
            "native_place": getattr(s.gate_entry, "native_place", None) if s.gate_entry else None,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "reference_type": getattr(s.gate_entry, "reference_type", None) if s.gate_entry else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "institution_id": str(s.program_details.institution_id) if s.program_details and s.program_details.institution_id else None,
            "department_id": str(s.program_details.department_id) if s.program_details and s.program_details.department_id else None,
        }
        for s in students
    ]'''

# Use regex to find and replace everything between "# Paginated data" and items = [...] definition
pattern = re.compile(r'    # Paginated data.*?for s in students\n    \]', re.DOTALL)
new_text = re.sub(pattern, replacer, text)

with open('src/apps/admission/routers.py', 'w') as f:
    f.write(new_text)

print("done")
