const fs = require('fs');
const content = fs.readFileSync('/home/prithivi/ERP/frontend/src/pages/admission/PreAdmission/AdmissionEntry.jsx', 'utf8');

const apiFuncs = [
  'getAdmissionVisitorByGatePassNo',
  'getAdmissionVisitors',
  'getAdmissionVisitor',
  'getReligions',
  'getCommunities',
  'getCastes',
  'getInstitutions',
  'getCourses',
  'getDepartments',
  'getAdmissionActiveYears',
  'getAcademicYearCourses',
  'getAdmissionEligiblePrograms',
  'getSchools',
  'getSchoolBlocks',
  'createAdmissionStudent',
  'updateAdmissionStudent',
  'getAdmissionStudent',
  'getAdmissionStudentByGatePass',
];

apiFuncs.forEach(func => {
  const count = content.split(func).length - 1;
  if (count <= 1) {
    console.log(`Unused: ${func}`);
  }
});
