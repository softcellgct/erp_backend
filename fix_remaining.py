import re

with open('src/apps/admission/routers.py', 'r') as f:
    text = f.read()

# Fix 1: Replace line 907 dict assignment
text = text.replace(
    '''            student_dict["department_name"] = department_name_map.get(str(student.department_id))
            student_dict["course_title"] = course_title_map.get(str(student.course_id))''',
    '''            student_dict["department_name"] = department_name_map.get(str(student.program_details.department_id)) if student.program_details and student.program_details.department_id else None
            student_dict["course_title"] = course_title_map.get(str(student.program_details.course_id)) if student.program_details and student.program_details.course_id else None'''
)

# Fix 2: Replace the block around 1690
def replacer_2(m):
    return '''        {
            "id": str(s.id),
            "name": s.personal_details.name if s.personal_details else None,
            "enquiry_number": s.enquiry_number,
            "application_number": s.application_number,
            "status": s.status,
            "student_mobile": s.personal_details.student_mobile if s.personal_details else None,
            "department_id": str(s.program_details.department_id) if s.program_details and s.program_details.department_id else None,
            "course_id": str(s.program_details.course_id) if s.program_details and s.program_details.course_id else None,
            "institution_id": str(s.program_details.institution_id) if s.program_details and s.program_details.institution_id else None,
        }
        for s in students'''

pattern_2 = re.compile(r'        \{\n            "id": str\(s\.id\),\n            "name": s\.name,\n.*?            "institution_id": str\(s\.institution_id\) if s\.institution_id else None,\n        \}\n        for s in students', re.DOTALL)
text = re.sub(pattern_2, replacer_2, text)

with open('src/apps/admission/routers.py', 'w') as f:
    f.write(text)

print("done")
