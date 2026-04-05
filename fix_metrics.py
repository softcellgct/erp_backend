import re

with open('src/apps/admission/routers.py', 'r') as f:
    text = f.read()

def metrics_replacer(m):
    return '''    # Source breakdown (from AdmissionGateEntry reference_type)
    from common.models.admission.admission_entry import AdmissionGateEntry
    stmt_source = select(
        AdmissionGateEntry.reference_type,
        func.count(AdmissionStudent.id)
    ).join(AdmissionStudent, AdmissionStudent.gate_entry_id == AdmissionGateEntry.id).where(
        AdmissionGateEntry.reference_type.isnot(None)
    ).group_by(AdmissionGateEntry.reference_type)'''

pattern = re.compile(r'    # Source breakdown.*?\.group_by\(AdmissionStudent\.reference_type\)', re.DOTALL)
text = re.sub(pattern, metrics_replacer, text)

# Also fix query_students inside list_enquiries
#     query_students = select(AdmissionStudent)
#     if source:
#         query_students = query_students.where(AdmissionStudent.source == source)
def enq_replacer(m):
    return '''    from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStudentPersonalDetails
    query_students = select(AdmissionStudent).outerjoin(AdmissionGateEntry).outerjoin(AdmissionStudentPersonalDetails).options(
        selectinload(AdmissionStudent.personal_details),
        selectinload(AdmissionStudent.gate_entry)
    )
    if source:
        # source doesn't exist, ignore or filter on reference_type
        pass
    if reference_type:
        query_students = query_students.where(AdmissionGateEntry.reference_type == reference_type)'''

pattern_2 = re.compile(r'    query_students = select\(AdmissionStudent\).*?query_students = query_students\.where\(AdmissionStudent\.reference_type == reference_type\)', re.DOTALL)
text = re.sub(pattern_2, enq_replacer, text)

with open('src/apps/admission/routers.py', 'w') as f:
    f.write(text)

print("done")
