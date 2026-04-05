import re

with open('src/apps/admission/routers.py', 'r') as f:
    text = f.read()

text = text.replace(
    'selectinload(AdmissionStudent.program_details)',
    'selectinload(AdmissionStudent.program_details), selectinload(AdmissionStudent.personal_details)'
)

# And fix all_enquiries
def repl_enq(m):
    return '''    all_enquiries = [{
        "id": str(s.id),
        "enquiry_number": s.enquiry_number,
        "name": s.personal_details.name if getattr(s, "personal_details", None) else None,
        "mobile": s.personal_details.student_mobile if getattr(s, "personal_details", None) else None,
        "status": s.status,
        "source": getattr(s, "source", None).value if getattr(s, "source", None) else None,
        "reference_type": getattr(s.gate_entry, "reference_type", None) if getattr(s, "gate_entry", None) else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in students]'''

text = re.sub(r'    all_enquiries = \[\{.*?\n    \} for s in students\]', repl_enq, text, flags=re.DOTALL)

with open('src/apps/admission/routers.py', 'w') as f:
    f.write(text)

print("done")
