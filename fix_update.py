import re

with open('src/apps/admission/routers.py', 'r') as f:
    text = f.read()

def replacer(m):
    return '''    # 1. Fetch Student
    stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details)).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if getattr(student, "is_fee_structure_locked", False):
        raise HTTPException(
            status_code=400,
            detail="Fee structure is locked for this student. Course/department change is not allowed.",
        )
        
    try:
        # 2. Update Student Course/Department
        if student.program_details:
            student.program_details.course_id = payload.course_id
            if payload.department_id:
                student.program_details.department_id = payload.department_id'''

pattern = re.compile(r'    # 1\. Fetch Student\n    stmt = select\(AdmissionStudent\)\.where\(AdmissionStudent\.id == student_id\).*?student\.department_id = payload\.department_id', re.DOTALL)
new_text = re.sub(pattern, replacer, text)

with open('src/apps/admission/routers.py', 'w') as f:
    f.write(new_text)

print("done")
