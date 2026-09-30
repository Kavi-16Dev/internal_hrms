{
    'name': 'Recruitment: Recruiter Role',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'Recruiter group: manage applications, interviews and offers; read-only jobs',
    'depends': ['hr_recruitment', 'ats_recruitment_customization', 'kavi_hr_job_custom'], # hr_contract_salary provides "Offer Letter Components" (Enterprise)
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
    ],
    'license': 'LGPL-3',
}
