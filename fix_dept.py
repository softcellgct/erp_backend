import re

with open('src/apps/admission/department_change_routers.py', 'r') as f:
    text = f.read()

def replacer(m):
    return '''    # Update student's department
    student_query = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details)).where(
        AdmissionStudent.id == change_request.student_id
    )
    result = await db.execute(student_query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    if getattr(student, "is_fee_structure_locked", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department change cannot be approved because the student's fee structure is locked.",
        )

    if getattr(student, "program_details", None):
        student.program_details.department_id = change_request.requested_department_id'''

pattern = re.compile(r'    # Update student\'s department\n    student_query = select\(AdmissionStudent\)\.where\(.*?student\.department_id = change_request\.requested_department_id', re.DOTALL)
new_text = re.sub(pattern, replacer, text)

with open('src/apps/admission/department_change_routers.py', 'w') as f:
    f.write(new_text)

print("done")
